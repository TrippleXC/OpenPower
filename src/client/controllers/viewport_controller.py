import arcade
import polars as pl
from typing import Optional, Callable
from enum import Enum, auto

from src.client.controllers.camera_controller import CameraController
from src.client.renderers.map_renderer import MapRenderer
from src.client.services.network_client_service import NetworkClient

class SelectionMode(Enum):
    REGION = auto()
    COUNTRY = auto()

class ViewportController:
    """
    Mediator between Raw Input, the Camera, and the Map Renderer.
    Responsibility: 'What happens when I click the map?'
    """
    def __init__(self, 
                 camera_ctrl: CameraController, 
                 world_camera: arcade.Camera2D,
                 map_renderer: MapRenderer,
                 net_client: NetworkClient,
                 on_selection_change: Callable[[Optional[int]], None]):
        
        self.cam_ctrl = camera_ctrl
        self.world_cam = world_camera
        self.renderer = map_renderer
        self.net = net_client
        self.on_selection_change = on_selection_change
        
        # Internal state to track panning
        self._is_panning = False
        self.selection_mode = SelectionMode.REGION

    def set_selection_mode(self, mode: SelectionMode):
        """Switches how clicks are interpreted."""
        self.selection_mode = mode
        # Reset current visual state to prevent artifacts
        self.renderer.set_highlight([]) 
        self.renderer.clear_country_highlight()
        self.on_selection_change(None)

    def on_mouse_press(self, x: float, y: float, button: int):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self._handle_selection(x, y)
        elif button in (arcade.MOUSE_BUTTON_RIGHT, arcade.MOUSE_BUTTON_MIDDLE):
            self._is_panning = True

    def on_mouse_release(self, x: float, y: float, button: int):
        if button in (arcade.MOUSE_BUTTON_RIGHT, arcade.MOUSE_BUTTON_MIDDLE):
            self._is_panning = False

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int):
        is_right_held = buttons & arcade.MOUSE_BUTTON_RIGHT
        is_middle_held = buttons & arcade.MOUSE_BUTTON_MIDDLE
        
        if self._is_panning or is_right_held or is_middle_held:
            self.cam_ctrl.pan(dx, dy)
            self.cam_ctrl.sync_with_arcade(self.world_cam)
            self._is_panning = True

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        self.cam_ctrl.zoom_scroll(scroll_y)
        self.cam_ctrl.sync_with_arcade(self.world_cam)

    def _handle_selection(self, screen_x: float, screen_y: float):
        """
        Translates screen click to world map selection.
        """
        world_pos = self.world_cam.unproject((screen_x, screen_y))
        
        # Query the renderer for the specific ID under the cursor
        region_id = self.renderer.get_region_id_at_world_pos(world_pos.x, world_pos.y)
        
        if region_id is None or region_id <= 0:
            self.renderer.clear_highlight()
            self.renderer.clear_country_highlight()
            self.on_selection_change(None)
            return

        if self.selection_mode == SelectionMode.REGION:
            # Highlight only the specific region clicked
            self.renderer.clear_country_highlight()
            self.renderer.set_highlight([region_id])
            self.on_selection_change(region_id)

        elif self.selection_mode == SelectionMode.COUNTRY:
            # Identify the owner and highlight all their regions
            state = self.net.get_state()
            owner_tag = "None"
            
            if "regions" in state.tables:
                try:
                    # Lookup owner in Polars table
                    row = state.tables["regions"].filter(pl.col("id") == region_id)
                    if not row.is_empty():
                        owner_tag = row["owner"][0]
                except Exception:
                    pass

            if owner_tag and owner_tag != "None":
                # Renderer dims the rest of the world and brightens the country
                self.renderer.set_country_highlight(owner_tag)
                # We still report the specific region ID to the UI for inspection data
                self.on_selection_change(region_id)
            else:
                # Land with no owner or water
                self.renderer.clear_country_highlight()
                self.renderer.set_highlight([region_id])
                self.on_selection_change(region_id)