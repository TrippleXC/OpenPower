import arcade
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, List, Tuple

# Import constants for Max/Min equations
from pyglet import gl 

from src.shared.map.region_atlas import RegionAtlas

class MapRenderer:
    """
    Handles map visualization including Terrain (Layer 0) and Regions (Layer 1).
    """

    def __init__(self, map_path: Path, terrain_path: Path, cache_dir: Path, preloaded_atlas: Optional[RegionAtlas] = None):
        self.map_path = map_path
        
        # --- Separate Layers ---
        self.terrain_list = arcade.SpriteList()
        self.overlay_list = arcade.SpriteList()
        
        # --- 1. Establish World Dimensions ---
        self.map_sprite = arcade.Sprite(map_path)
        
        self.width = self.map_sprite.width
        self.height = self.map_sprite.height
        
        self.map_sprite.center_x = self.width / 2
        self.map_sprite.center_y = self.height / 2
        self.map_sprite.alpha = 200
        
        self.overlay_list.append(self.map_sprite)

        # --- 2. Load Terrain ---
        if terrain_path and terrain_path.exists():
            self.terrain_sprite = arcade.Sprite(terrain_path)
            
            if self.terrain_sprite.width != self.width or self.terrain_sprite.height != self.height:
                print(f"[MapRenderer] Stretching terrain to {self.width}x{self.height}")
                self.terrain_sprite.width = self.width
                self.terrain_sprite.height = self.height
            
            self.terrain_sprite.center_x = self.width / 2
            self.terrain_sprite.center_y = self.height / 2
            self.terrain_list.append(self.terrain_sprite)

        # --- 3. Data Path ---
        if preloaded_atlas:
            self.atlas = preloaded_atlas
        else:
            self.atlas = RegionAtlas(str(map_path), str(cache_dir))
        
        print(f"[MapRenderer] Initialized. Map Size: {self.width}x{self.height}")

    def draw_map(self, mode: str = "add"):
        """
        Draws the map layers. 
        """
        # 1. Draw Terrain (Opaque Base)
        self.terrain_list.draw()

        # 2. Configure Overlay
        blend_func = None
        original_alpha = self.map_sprite.alpha

        try:
            if mode == "add":
                # [Add Mode with 50% Opacity]
                # Formula: Result = (Foreground * Alpha) + Background
                # This makes the region colors glow on top of the terrain, 
                # but only at half strength so we don't lose the mountains.
                self.map_sprite.alpha = 70
                blend_func = (gl.GL_SRC_ALPHA, gl.GL_ONE)
            
            elif mode == "multiply":
                # [Classic Strategy Look]
                self.map_sprite.alpha = 255 
                blend_func = (gl.GL_DST_COLOR, gl.GL_ZERO)
                
            else:
                # [Normal / Alpha Blending]
                self.map_sprite.alpha = 70
                blend_func = None

            # 3. Draw Regions
            if blend_func:
                self.overlay_list.draw(blend_function=blend_func)
            else:
                self.overlay_list.draw()

        finally:
            # 4. Restore Default State
            self.map_sprite.alpha = original_alpha
            gl.glBlendEquation(gl.GL_FUNC_ADD)

    # --- Utilities (Unchanged) ---
    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> Optional[int]:
        if not (0 <= world_x < self.width and 0 <= world_y < self.height):
            return None
        return self.atlas.get_region_at(int(world_x), int(self.height - world_y))

    def create_highlight_sprite(self, region_ids: List[int], color: Tuple[int, int, int] = (255, 255, 0)) -> Optional[arcade.Sprite]:
        if not region_ids: return None
        overlay_data, x_off, y_off = self.atlas.render_country_overlay(region_ids, border_color=color, thickness=2)
        if overlay_data is None: return None
        
        image = Image.fromarray(cv2.cvtColor(overlay_data, cv2.COLOR_BGRA2RGBA))
        texture = arcade.Texture(image, hash=f"highlight_{region_ids[0]}_{id(region_ids)}")
        sprite = arcade.Sprite(texture)
        small_h, small_w = overlay_data.shape[:2]
        sprite.center_x = x_off + small_w / 2
        sprite.center_y = self.height - (y_off + small_h / 2)
        return sprite

    def get_center(self) -> Tuple[float, float]:
        return (self.width / 2, self.height / 2)