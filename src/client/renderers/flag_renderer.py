import arcade
import os
from pathlib import Path
from typing import Dict, Optional

class FlagRenderer:
    """
    Service responsible for loading, caching, and providing Flag Textures.
    Uses absolute paths to ensure reliability across different environments.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FlagRenderer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # 1. Determine the Project Root (OpenPower folder)
        # We look for the directory containing the 'modules' folder.
        # This prevents path errors if the script is run from 'src' or elsewhere.
        current_path = Path(__file__).resolve()
        
        # Traverse up until we find the folder containing 'modules'
        self.project_root = current_path
        for parent in current_path.parents:
            if (parent / "modules").exists():
                self.project_root = parent
                break
        
        self.flags_dir = self.project_root / "modules" / "base" / "assets" / "flags"
        
        # 2. Setup Cache
        self._cache: Dict[str, Optional[arcade.Texture]] = {}
        self._fallback_tag = "XXX"
        self._initialized = True
        
        print(f"[FlagRenderer] Initialized. Root: {self.project_root}")
        print(f"[FlagRenderer] Flags directory: {self.flags_dir}")

    def get_texture(self, tag: str) -> Optional[arcade.Texture]:
        """
        Returns an Arcade Texture for the given country tag using absolute paths.
        """
        # Return from cache if already loaded (crucial for Arcade 3.0 performance)
        if tag in self._cache:
            return self._cache[tag]

        # 1. Build the absolute path for the specific flag
        flag_path = self.flags_dir / f"{tag}.png"

        # 2. Check if file exists, if not, try fallback
        if not flag_path.exists():
            print(f"[FlagRenderer] Warning: {tag}.png not found at {flag_path}. Using fallback.")
            flag_path = self.flags_dir / f"{self._fallback_tag}.png"

        # 3. If fallback also doesn't exist, cache None and return
        if not flag_path.exists():
            print(f"[FlagRenderer] Error: Specific and fallback flags missing at {flag_path}")
            self._cache[tag] = None
            return None

        # 4. Load the texture
        try:
            # arcade.load_texture accepts a Path object or a string
            texture = arcade.load_texture(flag_path)
            self._cache[tag] = texture
            return texture
        except Exception as e:
            print(f"[FlagRenderer] Failed to load {tag}: {e}")
            self._cache[tag] = None
            return None

    def clear_cache(self):
        """Clears the texture cache to free up VRAM."""
        self._cache.clear()