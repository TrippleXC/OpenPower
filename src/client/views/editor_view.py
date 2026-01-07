import arcade
from pyglet.math import Vec2

from src.shared.config import GameConfig
from src.client.services.network_client_service import NetworkClient
from src.client.renderers.map_renderer import MapRenderer
from src.client.ui.editor_layout import EditorLayout
from src.client.services.imgui_service import ImGuiService
from src.client.camera_controller import CameraController
from src.client.tasks.editor_loading_task import EditorContext

class EditorView(arcade.View):
    """
    The main visual interface for the Map Editor.
    Composes the Renderer, UI, and Network services into a cohesive interactive view.
    """

    def __init__(self, context: EditorContext, config: GameConfig):
        """
        Args:
            context: Pre-loaded assets (Atlas, Network, Paths) from the LoadingTask.
            config: Global game configuration.
        """
        super().__init__()
        self.game_config = config
        
        # --- 1. Composition: Logic Components ---
        # We use the pre-loaded network client connected to the session
        self.net = context.net_client
        self.imgui = ImGuiService(self.window)
        
        # --- 2. Composition: UI Layout ---
        # The EditorLayout handles specific ImGui windows (Inspector, Menu, etc.)
        self.ui_layout = EditorLayout(self.net)
        # Hook up the 'Focus' event so clicking a list item moves the camera
        self.ui_layout.on_focus_request = self.focus_on_coordinates
        
        # --- 3. Composition: Visual Components ---
        # Initialize Renderer using the PRE-LOADED Atlas (CPU work already done).
        self.map_renderer = MapRenderer(
            map_path=context.map_path, 
            terrain_path=context.terrain_path,
            cache_dir=config.cache_dir,
            preloaded_atlas=context.atlas
        )
        
        # --- 4. Composition: Camera System ---
        self.world_camera = arcade.Camera2D()
        
        # Center camera on map
        center_pos = self.map_renderer.get_center()
        self.camera_controller = CameraController(center_pos)
        
        # --- 5. Selection State ---
        self.selected_region_int_id = None
        self.highlight_layer = arcade.SpriteList()
        
        # Interaction Flags
        self.is_panning_map = False

    def on_resize(self, width: int, height: int):
        """Handle window resize for both UI and World Camera."""
        self.imgui.resize(width, height)
        self.world_camera.match_window()

    def on_show_view(self):
        """Called when the view becomes active."""
        self.camera_controller.update_arcade_camera(self.world_camera)
        
        # --- CRITICAL: Generate Political Layer ---
        # On startup, we fetch the country data and tell the renderer to paint the political map.
        self._refresh_political_data()

    def _refresh_political_data(self):
        """
        Fetches 'Regions' table and procedurally generates country colors 
        based on the 'owner' tag. (Temporary fix until countries.csv exists).
        """
        import hashlib # Used for generating colors from strings
        
        state = self.net.get_state()
        regions_df = state.get_table("regions")
        
        if regions_df.is_empty():
            print("[EditorView] Warning: Regions table is empty.")
            return

        if "owner" not in regions_df.columns:
            print("[EditorView] CRITICAL: 'owner' column missing in Regions table.")
            return

        # 1. Build Region Map {id: owner}
        # Polars Zip is fast
        region_map = dict(zip(regions_df["id"], regions_df["owner"]))
        
        # 2. Generate Temporary Colors for every unique Owner found
        # We use unique() to find all tags currently on the map (e.g., "UKR", "GER", "USA")
        unique_owners = regions_df["owner"].unique().to_list()
        
        color_map = {}
        for tag in unique_owners:
            if not tag or tag == "None": 
                # Transparent/Gray for unowned
                color_map[tag] = (0, 0, 0)
                continue
            
            # GENERATE COLOR: Hash the tag name to get 3 consistent bytes
            # This ensures "UKR" is always the same color, even after restart.
            hash_bytes = hashlib.md5(str(tag).encode('utf-8')).digest()
            
            # Use the first 3 bytes as RGB
            r = hash_bytes[0]
            g = hash_bytes[1]
            b = hash_bytes[2]
            
            color_map[tag] = (r, g, b)
            
        # 3. Send to Renderer
        # The atlas will now color regions based on these generated colors
        self.map_renderer.update_political_layer(region_map, color_map)

    def on_draw(self):
        """
        Main Render Loop.
        """
        self.clear()
        
        # 1. UI Update
        self.imgui.new_frame(1.0 / 60.0) 

        # 2. World Render
        self.world_camera.use()
        
        # --- DRAW MAP WITH SELECTED MODE ---
        # Get the internal mode string ("terrain" or "political") from UI Layout
        render_mode = self.ui_layout.get_current_render_mode()
        self.map_renderer.draw_map(mode=render_mode)
        
        # Draw selection highlight (Always on top, normal blending)
        self.highlight_layer.draw()
        
        # 3. UI Generation (Pass selection ID so Inspector knows what to show)
        self.ui_layout.render(self.selected_region_int_id, self.imgui.io.framerate)

        # 4. UI Render
        self.window.use() 
        self.imgui.render()

    # =========================================================================
    # Input Delegation
    # =========================================================================

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        # 1. Pass to ImGui first
        if self.imgui.on_mouse_press(x, y, button, modifiers):
            # If UI captured the mouse, stop world interaction
            self.is_panning_map = False 
            return

        # 2. Handle World Interaction
        if button == arcade.MOUSE_BUTTON_LEFT:
            self._handle_selection(x, y)
        
        if button == arcade.MOUSE_BUTTON_RIGHT or button == arcade.MOUSE_BUTTON_MIDDLE:
            self.is_panning_map = True

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int):
        if self.imgui.on_mouse_release(x, y, button, modifiers):
            return
        
        if button == arcade.MOUSE_BUTTON_RIGHT or button == arcade.MOUSE_BUTTON_MIDDLE:
            self.is_panning_map = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if self.imgui.on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            return

        if self.is_panning_map:
            self.camera_controller.pan(dx, dy)
            self.camera_controller.update_arcade_camera(self.world_camera)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.imgui.on_mouse_scroll(x, y, scroll_x, scroll_y):
            return
        
        self.camera_controller.zoom_scroll(scroll_y)
        self.camera_controller.update_arcade_camera(self.world_camera)
        
    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.imgui.on_mouse_motion(x, y, dx, dy)

    def on_key_press(self, symbol: int, modifiers: int):
        if self.imgui.on_key_press(symbol, modifiers):
            return

        # Hotkeys
        if symbol == arcade.key.S and (modifiers & arcade.key.MOD_CTRL):
            self.net.request_save()

    def on_key_release(self, symbol: int, modifiers: int):
        self.imgui.on_key_release(symbol, modifiers)

    def on_text(self, text: str):
        self.imgui.on_text(text)

    # --- Internal Helpers ---

    def _handle_selection(self, screen_x: int, screen_y: int):
        """Converts screen click to world coordinates and selects the region."""
        world_pos = self.world_camera.unproject((screen_x, screen_y))
        
        region_int_id = self.map_renderer.get_region_id_at_world_pos(world_pos.x, world_pos.y)
        
        if region_int_id is not None:
            self.selected_region_int_id = region_int_id
            
            # Generate visual highlight
            self.highlight_layer.clear()
            highlight_sprite = self.map_renderer.create_highlight_sprite(
                [region_int_id], 
                (255, 255, 0)
            )
            if highlight_sprite:
                self.highlight_layer.append(highlight_sprite)
        else:
            # Clicked on ocean/nothing
            self.selected_region_int_id = None
            self.highlight_layer.clear()

    def focus_on_coordinates(self, x: float, y: float):
        """Callback for UI list items to jump camera."""
        # Note: Atlas Y is usually Top-Left (Image space), World Y is Bottom-Left (OpenGL space). 
        # The region coordinates in the DB (x,y) are usually stored as Image coordinates from processing.
        # We must invert Y to match the World Camera.
        world_y = self.map_renderer.height - y
        self.camera_controller.jump_to(x, world_y)
        self.camera_controller.update_arcade_camera(self.world_camera)