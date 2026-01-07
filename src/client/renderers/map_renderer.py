import arcade
import cv2
import time
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from pyglet import gl 

from src.shared.map.region_atlas import RegionAtlas

class MapRenderer:
    """
    Handles map visualization layers: Terrain, Political boundaries, and UI Overlays.
    
    Architecture:
        - Layer 0 (Terrain): Static high-res image (The "Beauty" pass).
        - Layer 1 (Political): Generated RGBA texture showing country colors (The "Info" pass).
        - Layer 2 (Debug): The raw regions map (useful for checking IDs).
        - Layer 3 (Overlay): Interactive highlights (The "UI" pass).
        
    This separation allows toggling views (Terrain vs Political) without reloading data.
    """

    def __init__(self, map_path: Path, terrain_path: Path, cache_dir: Path, preloaded_atlas: Optional[RegionAtlas] = None):
        """
        Args:
            map_path: Path to 'regions.png' (the data map).
            terrain_path: Path to 'terrain.jpg' (the visual map).
            cache_dir: Where to store/load calculation caches.
            preloaded_atlas: Optional injection of an existing Atlas (for dependency injection).
        """
        self.map_path = map_path
        
        # --- Sprite Lists (Layers) ---
        # Arcade optimizes drawing by batching sprites in lists.
        self.terrain_list = arcade.SpriteList()
        self.political_list = arcade.SpriteList()
        self.debug_list = arcade.SpriteList()
        self.overlay_list = arcade.SpriteList()
        
        # --- 1. Initialize Dimensions & Debug Layer ---
        # We load the raw regions.png as a sprite so we can draw it in 'Debug' mode.
        # This determines the authoritative size of the world.
        self.region_debug_sprite = arcade.Sprite(map_path)
        self.width = self.region_debug_sprite.width
        self.height = self.region_debug_sprite.height
        
        # Center the debug sprite (Arcade defaults to bottom-left 0,0, but usually we center maps)
        self.region_debug_sprite.center_x = self.width / 2
        self.region_debug_sprite.center_y = self.height / 2
        self.debug_list.append(self.region_debug_sprite)
        
        # --- 2. Load Terrain (Base Layer) ---
        if terrain_path and terrain_path.exists():
            self.terrain_sprite = arcade.Sprite(terrain_path)
            
            # Ensure terrain matches region map size exactly
            if self.terrain_sprite.width != self.width or self.terrain_sprite.height != self.height:
                print(f"[MapRenderer] Resizing terrain to match map: {self.width}x{self.height}")
                self.terrain_sprite.width = self.width
                self.terrain_sprite.height = self.height
            
            self.terrain_sprite.center_x = self.width / 2
            self.terrain_sprite.center_y = self.height / 2
            self.terrain_list.append(self.terrain_sprite)
        else:
            print("[MapRenderer] Warning: No terrain found. Using debug map as placeholder.")
            # If no terrain, we add the debug sprite to the terrain list so *something* shows up
            # We clone it so we can change opacity independently
            fallback = arcade.Sprite(map_path)
            fallback.center_x = self.width / 2
            fallback.center_y = self.height / 2
            fallback.alpha = 50 # Dim it
            self.terrain_list.append(fallback)

        # --- 3. Initialize Data Atlas ---
        # If the server/main logic already created an atlas, we reuse it to save memory.
        if preloaded_atlas:
            self.atlas = preloaded_atlas
        else:
            self.atlas = RegionAtlas(str(map_path), str(cache_dir))
        
        # Placeholder for the dynamic political layer sprite
        self.political_sprite: Optional[arcade.Sprite] = None
        
        print(f"[MapRenderer] Initialized. World Size: {self.width}x{self.height}")

    def update_political_layer(self, 
                             region_ownership: Dict[int, str], 
                             country_colors: Dict[str, Tuple[int, int, int]]):
        """
        Regenerates the political map texture based on new game state data.
        
        When to call:
            - On game start.
            - After significant map changes (e.g., peace treaty, annexation).
            
        Args:
            region_ownership: {region_id: 'TAG'}
            country_colors: {'TAG': (R, G, B)}
        """
        print("[MapRenderer] Rebuilding Political Layer Texture...")
        
        # 1. Ask Atlas to generate the raw pixel array
        raw_image = self.atlas.generate_political_view(region_ownership, country_colors)
        
        # 2. Convert raw bytes to an Arcade Texture
        # We use a timestamp in the hash to force Arcade to treat this as a NEW texture,
        # ensuring the GPU updates and doesn't use a cached version.
        image = Image.fromarray(raw_image) # Assumes RGBA input from Atlas
        texture = arcade.Texture(image, hash=f"pol_layer_{time.time()}")
        
        # 3. Update the Sprite
        if self.political_sprite:
            self.political_list.remove(self.political_sprite)
            
        self.political_sprite = arcade.Sprite(texture)
        self.political_sprite.center_x = self.width / 2
        self.political_sprite.center_y = self.height / 2
        
        self.political_list.append(self.political_sprite)

    def draw_map(self, mode: str = "terrain"):
        """
        Renders the map layers to the screen.
        
        Args:
            mode (str): 
                - 'terrain': Shows physical map. Political borders are hidden.
                - 'political': Shows physical map with semi-transparent political overlay.
                - 'debug_regions': Shows the raw region ID map (useful for debugging).
        """
        # 1. Base Layer
        # If we are in DEBUG mode, we draw the colorful regions.png
        if mode == "debug_regions":
            self.debug_list.draw()
        else:
            # Otherwise we draw the artistic terrain
            self.terrain_list.draw()

        # 2. Context Layer (Political Overlay)
        # This is drawn ON TOP of the terrain if the mode is selected
        if mode == "political":
            if self.political_sprite:
                self.political_list.draw()
            else:
                # If the layer hasn't been generated yet (e.g., loading screen), skip it.
                pass

        # 3. Overlay Layer (Selection/Highlights)
        # We use Additive Blending (GL_ONE) to make the selection outlines "glow" 
        # and ensure they are visible on both dark and light terrains.
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        self.overlay_list.draw()
        
        # Reset blending to default (Alpha Interpolation) to avoid messing up UI rendering later
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

    # =========================================================================
    # Utilities: Coordinate translation & Highlighting
    # =========================================================================

    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> Optional[int]:
        """Translates world coordinates (Arcade) to map coordinates (Atlas)."""
        # Arcade (0,0) is Bottom-Left. NumPy/Image (0,0) is usually Top-Left.
        # The Atlas.get_region_at expects (x, y) where y is from Top.
        if not (0 <= world_x < self.width and 0 <= world_y < self.height):
            return None
        
        # Invert Y because images are stored Top-Down, but Arcade renders Bottom-Up
        map_y = self.height - world_y
        return self.atlas.get_region_at(int(world_x), int(map_y))

    def create_highlight_sprite(self, region_ids: List[int], color: Tuple[int, int, int] = (255, 255, 0)) -> Optional[arcade.Sprite]:
        """
        Creates a temporary sprite highlighting the borders of specific regions.
        Useful for mouse hover effects or selecting a country.
        """
        if not region_ids: return None
        
        # Get visual data from Atlas
        overlay_data, x_off, y_off = self.atlas.render_country_overlay(region_ids, border_color=color, thickness=3)
        
        if overlay_data is None: return None
        
        # Convert to Texture
        image = Image.fromarray(overlay_data) 
        
        # Unique hash prevents caching collisions for dynamic highlights
        texture = arcade.Texture(image, hash=f"highlight_{region_ids[0]}_{time.time()}")
        sprite = arcade.Sprite(texture)
        
        # Positioning:
        # Atlas gives us Top-Left offset (x_off, y_off).
        # We need to calculate Center X/Y for Arcade.
        small_h, small_w = overlay_data.shape[:2]
        
        sprite.center_x = x_off + (small_w / 2)
        # Invert Y for Arcade positioning
        sprite.center_y = self.height - (y_off + (small_h / 2))
        
        return sprite

    def get_center(self) -> Tuple[float, float]:
        return (self.width / 2, self.height / 2)