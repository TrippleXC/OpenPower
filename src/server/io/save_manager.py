import dataclasses
import shutil
import polars as pl
import orjson
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from src.server.state import GameState
from src.shared.config import GameConfig

class SaveManager:
    """
    Manages the lifecycle of game save files using high-performance serialization.
    Implements Atomic Saves to prevent corruption.
    """
    
    def __init__(self, config: GameConfig):
        self.config = config
        self.save_root = config.project_root / "user_data" / "saves"
        self.save_root.mkdir(parents=True, exist_ok=True)

    def save_game(self, state: GameState, save_name: str) -> bool:
        """
        Serializes the GameState to disk atomically using Parquet and orjson.
        """
        # Sanitize name
        safe_name = "".join(c for c in save_name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not safe_name:
            print(f"[SaveManager] Error: Invalid save name '{save_name}'")
            return False

        target_path = self.save_root / safe_name
        temp_path = self.save_root / f"{safe_name}_tmp"

        print(f"[SaveManager] Saving '{safe_name}'...")

        try:
            # 1. Clean Workspace
            if temp_path.exists():
                shutil.rmtree(temp_path)
            temp_path.mkdir()

            # 2. Reflection: Gather Data
            meta_data = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
            }

            for field in dataclasses.fields(state):
                key = field.name
                value = getattr(state, key)

                # A. Polars DataFrames -> Parquet
                if isinstance(value, pl.DataFrame):
                    value.write_parquet(temp_path / f"{key}.parquet")

                # B. Dict[str, DataFrame] -> Folder of Parquets
                elif isinstance(value, dict) and value and isinstance(next(iter(value.values())), pl.DataFrame):
                    sub_dir = temp_path / key
                    sub_dir.mkdir(exist_ok=True)
                    for tbl_name, df in value.items():
                        df.write_parquet(sub_dir / f"{tbl_name}.parquet")

                # C. Dataclasses -> Dict (for JSON)
                elif dataclasses.is_dataclass(value):
                    meta_data[key] = dataclasses.asdict(value)

                # D. Primitives -> JSON
                else:
                    meta_data[key] = value

            # 3. Write Metadata (orjson for speed)
            with open(temp_path / "meta.json", "wb") as f:
                f.write(orjson.dumps(meta_data, option=orjson.OPT_INDENT_2))

            # 4. Atomic Commit (Rename)
            if target_path.exists():
                shutil.rmtree(target_path)
            temp_path.rename(target_path)
            
            print(f"[SaveManager] Saved '{safe_name}' successfully.")
            return True

        except Exception as e:
            print(f"[SaveManager] Critical Save Failure: {e}")
            if temp_path.exists():
                shutil.rmtree(temp_path)
            return False

    def get_save_list(self) -> List[Dict[str, Any]]:
        """
        Returns a sorted list of saves for the UI.
        """
        saves = []
        for p in self.save_root.iterdir():
            if not p.is_dir(): continue
                
            meta_file = p / "meta.json"
            if meta_file.exists():
                try:
                    # Quick read of just the JSON for listing
                    with open(meta_file, "rb") as f:
                        data = orjson.loads(f.read())
                        saves.append({
                            "name": p.name,
                            "timestamp": data.get("timestamp", ""),
                            # Robustly handle potential missing keys
                            "tick": data.get("globals", {}).get("tick", 0)
                        })
                except Exception:
                    continue
                    
        return sorted(saves, key=lambda x: x["timestamp"], reverse=True)

    def delete_save(self, save_name: str) -> bool:
        """
        Permanently removes a save.
        """
        target_path = self.save_root / save_name
        if target_path.exists() and target_path.is_dir():
            try:
                shutil.rmtree(target_path)
                print(f"[SaveManager] Deleted save '{save_name}'.")
                return True
            except Exception as e:
                print(f"[SaveManager] Failed to delete '{save_name}': {e}")
                return False
        return False