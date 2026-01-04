import polars as pl
import rtoml
from pathlib import Path
from typing import List, Dict, Any

from src.server.state import GameState

class DataLoader:
    """
    Acts as a 'Compiler' that transforms Human-Readable Source Data (TSV, TOML)
    into Machine-Optimized Game State (Polars DataFrames).
    
    Responsibilities:
    1. Validation: Ensures required files exist.
    2. ETL (Extract, Transform, Load): Converts formats (e.g., Hex strings -> Int32 IDs).
    3. Aggregation: Merges scattered config files (individual country TOMLs) into single tables.
    """

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        # TODO: Make the module path configurable to support mod loading orders (modules.json).
        self.data_dir = root_dir / "modules" / "base" / "data"

    def load_initial_state(self) -> GameState:
        """
        Orchestrates the loading of all core game data.
        Returns a fully initialized GameState object ready for the simulation loop.
        """
        print("[DataLoader] Starting compilation of source data to memory...")
        state = GameState()
        
        # 1. Load Map Geography (Regions)
        regions_path = self.data_dir / "map" / "regions.tsv"
        if regions_path.exists():
            regions_df = self._load_regions(regions_path)
            state.update_table("regions", regions_df)
        else:
            print(f"[DataLoader] CRITICAL ERROR: Regions definition not found at {regions_path}")

        # 2. Load Political Entities (Countries)
        countries_dir = self.data_dir / "countries"
        if countries_dir.exists():
            countries_df = self._load_countries(countries_dir)
            state.update_table("countries", countries_df)
        else:
            print(f"[DataLoader] WARNING: Countries directory not found at {countries_dir}")
        
        print(f"[DataLoader] Compilation complete. Loaded tables: {list(state.tables.keys())}")
        return state

    def _load_regions(self, path: Path) -> pl.DataFrame:
        """
        Loads region definitions and performs critical texture ID pre-calculation.
        """
        # Read the raw TSV. We expect columns: id, hex, name, owner, type, etc.
        # Strict parsing is disabled to handle potential extra columns from mods safely.
        df = pl.read_csv(path, separator="\t", ignore_errors=True)

        # Optimization: Pre-calculate the 'color_id' used for GPU/Texture lookups.
        #
        # Context:
        # The map is rendered using a color-coded PNG. Reading pixel values via OpenCV 
        # usually results in a BGR layout. To identify a region instantly on mouse click, 
        # we need to convert the TSV's Hex string (#RRGGBB) into the integer format 
        # that matches the loaded texture data.
        #
        # Formula: Packed_Int32 = B + (G << 8) + (R << 16)
        
        # 1. Clean the string (remove '#')
        df = df.with_columns(pl.col("hex").str.strip_prefix("#").alias("_hex"))
        
        # 2. Vectorized channel extraction and conversion.
        # We use map_elements here for compatibility, though distinct parsing expressions 
        # might be faster in future Polars versions.
        df = df.with_columns([
            pl.col("_hex").str.slice(0, 2).map_elements(lambda x: int(x, 16), return_dtype=pl.UInt32).alias("_r"),
            pl.col("_hex").str.slice(2, 2).map_elements(lambda x: int(x, 16), return_dtype=pl.UInt32).alias("_g"),
            pl.col("_hex").str.slice(4, 2).map_elements(lambda x: int(x, 16), return_dtype=pl.UInt32).alias("_b"),
        ])
        
        # 3. Apply bitwise packing logic.
        df = df.with_columns(
            (pl.col("_b") + (pl.col("_g") * 256) + (pl.col("_r") * 65536)).cast(pl.Int32).alias("color_id")
        )
        
        # Cleanup intermediate columns to keep memory footprint low
        return df.drop(["_hex", "_r", "_g", "_b"])

    def _load_countries(self, directory: Path) -> pl.DataFrame:
        """
        Aggregates individual TOML configuration files into a single DataFrame.
        This allows modders to add countries by simply dropping a new file into the folder.
        """
        data_list: List[Dict[str, Any]] = []
        
        # Iterate over all .toml files (e.g., ua.toml, usa.toml)
        for file_path in directory.glob("*.toml"):
            try:
                data = rtoml.load(file_path)
                
                # Enforce implicit ID convention:
                # If 'id' is missing in the file, use the filename (without extension).
                # This prevents errors if a modder forgets the ID field.
                if "id" not in data:
                    data["id"] = file_path.stem
                    
                data_list.append(data)
            except Exception as e:
                # We log the error but continue loading other files to make the engine robust.
                print(f"[DataLoader] Failed to parse country file {file_path}: {e}")
        
        if not data_list:
            return pl.DataFrame()
            
        # Convert list of dicts to DataFrame. Polars handles missing keys by creating nulls,
        # which is perfect for sparse data (e.g., some countries might not have specific modifiers).
        return pl.from_dicts(data_list)