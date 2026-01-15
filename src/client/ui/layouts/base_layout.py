import arcade
from typing import Optional, Any, Callable
from src.client.services.network_client_service import NetworkClient
from src.client.ui.panels.region_inspector import RegionInspectorPanel
from src.client.utils.coords_util import image_to_world
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class BaseLayout:
    """
    Shared infrastructure for all UI Layouts (Editor & Game).
    
    Responsibilities:
    - Initializing the UI Composer (Theme manager).
    - Managing shared panels (like the Region Inspector).
    - bridging the gap between UI events (Clicking 'Focus') and 
      Viewport Controllers (Moving the camera).
    """
    def __init__(self, net_client: NetworkClient, viewport_ctrl: Any):
        self.net = net_client
        self.viewport_ctrl = viewport_ctrl
        self.composer = UIComposer(GAMETHEME)
        
        # Shared Inspector Panel (Used in both Editor and Game)
        # We instantiate it once here to keep its internal caching state alive.
        self.inspector = RegionInspectorPanel()

    def render_inspector(self, selected_region_id: Optional[int], state: Any):
        """
        Helper to render the inspector.
        
        We pass a lambda for the 'on_focus_request' callback.
        This keeps the Inspector UI unaware of the Camera/Viewport logic.
        """
        # The inspector needs:
        # 1. The ID to show.
        # 2. The GameState (to look up data).
        # 3. A callback to run when the user clicks "Focus Camera".
        self.inspector.render(selected_region_id, state, self._on_focus_region)

    def _on_focus_region(self, region_id: int, image_x: float, image_y: float):
        """
        Callback triggered by the Inspector Panel.
        Converts raw map image coordinates -> World Coordinates and moves camera.
        """
        # 1. Force the selection (visual highlight)
        self.viewport_ctrl.select_region_by_id(region_id)
        
        # 2. Convert Image Coords (Top-Left) -> World Coords (Bottom-Left)
        # We need the map height for the Y-inversion.
        map_height = self.viewport_ctrl.renderer.height
        world_x, world_y = image_to_world(image_x, image_y, map_height)
        
        # 3. Command the Camera Controller to jump
        self.viewport_ctrl.cam_ctrl.jump_to(world_x, world_y)
        
        # 4. Sync immediately so there is no visual lag
        self.viewport_ctrl.cam_ctrl.sync_with_arcade(self.viewport_ctrl.world_cam)