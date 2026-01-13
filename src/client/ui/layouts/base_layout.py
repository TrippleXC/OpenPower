from typing import Optional, Any
from src.client.services.network_client_service import NetworkClient
from src.client.ui.panels.region_inspector import RegionInspectorPanel
from src.client.utils.coords_util import image_to_world
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class BaseLayout:
    """
    Shared logic for all UI Layouts (Editor & Game).
    Handles common services like Network, Viewport Control, and the Region Inspector.
    """
    def __init__(self, net_client: NetworkClient, viewport_ctrl: Any):
        self.net = net_client
        self.viewport_ctrl = viewport_ctrl
        self.composer = UIComposer(GAMETHEME)
        
        # Shared Inspector Panel (Used in both Editor and Game)
        self.inspector = RegionInspectorPanel()

    def render_inspector(self, selected_region_id: Optional[int], state: Any):
        """
        Helper to render the inspector with the correct callback.
        """
        self.inspector.render(selected_region_id, state, self._on_focus_region)

    def _on_focus_region(self, region_id: int, x: float, y: float):
        """
        Callback passed to the Inspector.
        """
        self.viewport_ctrl.select_region_by_id(region_id)
        
        # 1. Convert Image Coords -> World Coords
        map_height = self.viewport_ctrl.renderer.height
        world_x, world_y = image_to_world(x, y, map_height)
        
        # 2. Jump Camera (Centering is inherent to jump_to)
        self.viewport_ctrl.cam_ctrl.jump_to(world_x, world_y)
        self.viewport_ctrl.cam_ctrl.sync_with_arcade(self.viewport_ctrl.world_cam)