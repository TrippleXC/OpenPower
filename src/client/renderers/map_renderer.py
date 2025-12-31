import arcade
from PIL import Image
from pathlib import Path

class MapRenderer:
    """
    Handles regions map visualization and pixel-level data access.
    Employs a hybrid approach: Arcade Sprites for efficient GPU rendering 
    and PIL Images for fast CPU-side pixel lookups.
    """
    def __init__(self, map_path: Path):
        self.sprite_list = arcade.SpriteList()
        self.source_image = None
        self.width = 0
        self.height = 0
        
        if map_path.exists():
            try:
                # 1. GPU Path: Efficiently render the map texture.
                sprite = arcade.Sprite(map_path)
                # Center the sprite so that (0,0) world coordinates align 
                # with the bottom-left of the image.
                sprite.center_x = sprite.width / 2
                sprite.center_y = sprite.height / 2
                self.sprite_list.append(sprite)
                
                # 2. CPU Path: Store the image in memory for coordinate-to-color lookups.
                self.source_image = Image.open(map_path)
                self.width = self.source_image.width
                self.height = self.source_image.height
                
                print(f"[MapRenderer] Loaded map: {self.width}x{self.height}")
            except Exception as e:
                print(f"[MapRenderer] Error loading map: {e}")
        else:
            print(f"[MapRenderer] Error: Map file not found at {map_path}")

    def draw(self):
        """Renders the map sprite list."""
        self.sprite_list.draw()

    def get_color_at_world_pos(self, world_x: float, world_y: float) -> str:
        """
        Retrieves the HEX color code from the map at the given world coordinates.
        Returns None if the coordinates are outside the map boundaries.
        """
        if not self.source_image:
            return None

        # Bounds check to prevent out-of-range pixel access.
        if 0 <= world_x < self.width and 0 <= world_y < self.height:
            # Convert world space (y-up) to image space (y-down) coordinates.
            img_x = int(world_x)
            img_y = int(self.height - world_y)
            
            try:
                color = self.source_image.getpixel((img_x, img_y))
                # Convert the RGB(A) tuple to a standard CSS-style HEX string.
                return "#{:02x}{:02x}{:02x}".format(color[0], color[1], color[2])
            except Exception:
                return None
        return None

    def get_center(self) -> arcade.math.Vector2:
        """Calculates the geometric center of the map for camera initialization."""
        return arcade.math.Vector2(self.width / 2, self.height / 2)
