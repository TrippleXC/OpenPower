import arcade
from pathlib import Path

from src.client.camera_controller import CameraController
from src.client.renderers.map_renderer import MapRenderer

# Project root calculation to resolve asset paths relative to the source.
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MAP_PATH = PROJECT_ROOT / "modules" / "base" / "assets" / "maps" / "regions.png"

class EditorView(arcade.View):
    """
    Editor Mode view.
    Provides tools for editing maps, scenarios, and data.
    """
    def __init__(self):
        super().__init__()
        
        self.camera_controller = None
        self.map_renderer = None
        
        self.world_camera = None
        self.ui_camera = None

    def setup(self):
        """Initializes scene resources and components."""
        width = self.window.width
        height = self.window.height
        
        self.world_camera = arcade.Camera(width, height)
        self.ui_camera = arcade.Camera(width, height)
        
        self.map_renderer = MapRenderer(MAP_PATH)
        
        # Initialize camera at the map's center for immediate visibility.
        start_pos = self.map_renderer.get_center()
        self.camera_controller = CameraController(start_pos)
        
        # Initial camera projection update.
        self.camera_controller.update_arcade_camera(self.world_camera, width, height)
        print("[EditorView] Setup complete.")

    def on_show_view(self):
        """Called when this view becomes active."""
        self.setup()
        # Grey background helps distinguish the editor from the black gameplay background.
        self.window.background_color = arcade.color.DARK_SLATE_GRAY

    def on_draw(self):
        """Main rendering loop."""
        self.clear()
        
        # 1. World Layer (Map and entities)
        self.world_camera.use()
        if self.map_renderer:
            self.map_renderer.draw()
            
        # 2. UI Layer (Overlays and menus)
        self.ui_camera.use()
        # Debug information overlay
        arcade.draw_text("EDITOR MODE", 10, self.window.height - 30, arcade.color.WHITE, 20)
        arcade.draw_text("Controls: Scroll to Zoom, Middle Click to Pan, Left Click to Select", 
                         10, self.window.height - 60, arcade.color.WHITE, 12)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self._handle_selection(x, y)

    def _handle_selection(self, screen_x: int, screen_y: int):
        # Convert screen-space mouse coordinates to world-space coordinates 
        # based on current camera zoom and position.
        wx, wy = self.camera_controller.screen_to_world(
            screen_x, screen_y, self.window.width, self.window.height
        )
        
        # Retrieve the color code from the regions map at the calculated world position.
        color_hex = self.map_renderer.get_color_at_world_pos(wx, wy)
        
        if color_hex:
            if color_hex not in ["#ffffff", "#000000"]:
                print(f"[Editor] Region Selected: {color_hex}")
            else:
                print("[Editor] Clicked border")

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera_controller.scroll(scroll_y)
        self.camera_controller.update_arcade_camera(
            self.world_camera, self.window.width, self.window.height
        )

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons == arcade.MOUSE_BUTTON_MIDDLE:
            self.camera_controller.drag(dx, dy)
            self.camera_controller.update_arcade_camera(
                self.world_camera, self.window.width, self.window.height
            )

    def on_resize(self, width, height):
        self.world_camera.resize(width, height)
        self.ui_camera.resize(width, height)
        if self.camera_controller:
            self.camera_controller.update_arcade_camera(self.world_camera, width, height)
