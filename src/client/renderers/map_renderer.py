import arcade
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, List, Tuple

from src.shared.map.region_atlas import RegionAtlas

class MapRenderer:
    """
    Handles map visualization and interacts with the shared RegionAtlas for data.
    
    Responsibilities:
    1. Renders the main map texture (GPU).
    2. Acts as a bridge between World Coordinates (Arcade) and Image Coordinates (Atlas).
    3. Generates dynamic textures (e.g., selection borders) from Atlas data.
    """

    def __init__(self, map_path: Path, cache_dir: Path):
        self.map_path = map_path
        
        # 1. GPU Path: Main Map Sprite
        self.sprite_list = arcade.SpriteList()
        self.map_sprite = arcade.Sprite(map_path)
        
        # Center sprite so (0,0) world matches bottom-left of image
        self.map_sprite.center_x = self.map_sprite.width / 2
        self.map_sprite.center_y = self.map_sprite.height / 2
        self.sprite_list.append(self.map_sprite)

        # 2. Data Path: Shared Region Atlas (NumPy/OpenCV)
        # Convert Path objects to strings for cv2/os compatibility if needed
        self.atlas = RegionAtlas(str(map_path), str(cache_dir))
        
        self.width = self.atlas.width
        self.height = self.atlas.height

        print(f"[MapRenderer] Initialized. Map Size: {self.width}x{self.height}")

    def draw_map(self):
        """Draws the base map layer."""
        self.sprite_list.draw()

    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> Optional[int]:
        """
        Converts World Coordinates (Bottom-Left origin) to Atlas Coordinates (Top-Left origin)
        and retrieves the region ID.
        """
        # 1. Bounds check
        if not (0 <= world_x < self.width and 0 <= world_y < self.height):
            return None

        # 2. Coordinate Conversion: Flip Y axis
        # Arcade (y=0 is bottom) -> Image (y=0 is top)
        img_x = int(world_x)
        img_y = int(self.height - world_y)

        return self.atlas.get_region_at(img_x, img_y)

    def get_color_hex_at_world_pos(self, world_x: float, world_y: float) -> Optional[str]:
        """Helper to get HEX color string for UI/Debugging."""
        img_x = int(world_x)
        img_y = int(self.height - world_y)
        
        rgb = self.atlas.get_color_at(img_x, img_y)
        if rgb:
            return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
        return None

    def create_highlight_sprite(self, region_ids: List[int], color: Tuple[int, int, int] = (255, 255, 0)) -> Optional[arcade.Sprite]:
        """
        Generates a transparent Arcade Sprite containing only the borders of the specified regions.
        """
        if not region_ids:
            return None

        # 1. Get optimized overlay data (Cropped image + Offsets)
        # Returns: (small_image, x_offset_in_atlas, y_offset_in_atlas)
        overlay_data, x_off, y_off = self.atlas.render_country_overlay(region_ids, border_color=color, thickness=3)

        if overlay_data is None:
            return None

        # 2. Convert BGRA (OpenCV) to RGBA (PIL/Arcade)
        overlay_rgba = cv2.cvtColor(overlay_data, cv2.COLOR_BGRA2RGBA)

        # 3. Create PIL Image
        image = Image.fromarray(overlay_rgba)

        # 4. Create Texture and Sprite
        texture_name = f"highlight_{region_ids[0]}_{id(region_ids)}"
        texture = arcade.Texture(image, hash=texture_name)
        
        sprite = arcade.Sprite(texture)
        
        # 5. Position Sprite Correctly
        # We need to calculate where the center of this small sprite is in the World.
        
        # Dimensions of the small cropped image
        small_h, small_w = overlay_data.shape[:2]
        
        # Center in Image Coordinates (Top-Left origin)
        # The sprite starts at (x_off, y_off) in the big map
        center_img_x = x_off + small_w / 2
        center_img_y = y_off + small_h / 2
        
        # Convert to Arcade World Coordinates (Bottom-Left origin)
        # Flip Y: world_y = height - img_y
        sprite.center_x = center_img_x
        sprite.center_y = self.height - center_img_y
        
        return sprite

    def get_center(self) -> arcade.math.Vector2:
        """Returns the center of the map as a simple tuple."""
        return (self.width / 2, self.height / 2)