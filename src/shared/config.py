from pathlib import Path
from typing import List

class GameConfig:
    """
    Central configuration handler for the OpenPower engine.
    
    Responsibilities:
    1. Resolve file paths dynamically (removing hardcoded strings).
    2. Provide access to Data and Asset directories.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        
        # Standard directory structure definitions
        self.modules_dir = project_root / "modules"
        self.cache_dir = project_root / ".cache"
        
        # Default load order.
        # This will be populated/overwritten by ModManager in GameSession.
        self.active_mods: List[str] = ["base"]

    def get_data_dirs(self) -> List[Path]:
        """
        Returns a list of data directories for all active mods.
        Used by DataLoader to scan for content.
        """
        paths = []
        for mod in self.active_mods:
            p = self.modules_dir / mod / "data"
            if p.exists():
                paths.append(p)
        return paths

    def get_write_data_dir(self) -> Path:
        """
        Returns the directory where the Editor should save changes.
        For MVP, we save to the 'base' module.
        """
        return self.modules_dir / "base" / "data"

    def get_asset_path(self, relative_path: str) -> Path:
        """
        Finds an asset (image/sound) by searching through active mods.
        """
        # Search in reverse order (Mods override Base)
        for mod in reversed(self.active_mods):
            candidate = self.modules_dir / mod / "assets" / relative_path
            if candidate.exists():
                return candidate
        
        # Fallback
        return self.modules_dir / "base" / "assets" / relative_path