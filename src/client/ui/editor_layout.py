from imgui_bundle import imgui
import polars as pl
from typing import Optional, Callable
from src.client.services.network_client_service import NetworkClient

class EditorLayout:
    """
    Manages the ImGui layout for the Editor.
    """
    
    def __init__(self, net_client: NetworkClient):
        self.net = net_client
        
        # Events
        self.on_focus_request: Optional[Callable[[float, float], None]] = None 
        
        # UI State
        self.show_region_list = False
        
        # Map Visualization Settings
        # This string is read by the EditorView every frame
        self.map_mode = "add" 
        self.available_modes = ["normal", "multiply", "add"]

    def render(self, selected_region_int_id: Optional[int], fps: float):
        """Main entry point to draw all editor UI panels."""
        self._render_menu()
        self._render_inspector(selected_region_int_id)
        
        if self.show_region_list:
            self._render_region_list()
        
        # Debug / Info Overlay
        self._render_debug_overlay(fps)

    def _render_menu(self):
        """Draws the main menu bar."""
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("File"):
                if imgui.menu_item("Save Regions", "Ctrl+S")[0]:
                    self.net.request_save()
                imgui.end_menu()
                
            if imgui.begin_menu("View"):
                # Checkbox for Region List
                _, self.show_region_list = imgui.menu_item("Region List", "", self.show_region_list)
                
                imgui.separator()
                
                # --- Map Blending Dropdown ---
                imgui.text("Map Mode:")
                if imgui.begin_combo("##map_mode", self.map_mode):
                    for mode in self.available_modes:
                        is_selected = (mode == self.map_mode)
                        if imgui.selectable(mode, is_selected)[0]:
                            self.map_mode = mode
                        
                        # Set default focus
                        if is_selected:
                            imgui.set_item_default_focus()
                    imgui.end_combo()

                imgui.end_menu()
                
            imgui.end_main_menu_bar()

    def _render_debug_overlay(self, fps: float):
        imgui.set_next_window_pos((10, 50), imgui.Cond_.first_use_ever)
        imgui.begin("Debug", flags=imgui.WindowFlags_.always_auto_resize | imgui.WindowFlags_.no_decoration)
        imgui.text(f"FPS: {fps:.0f}" if fps > 0 else "--")
        imgui.text(f"Mode: {self.map_mode.upper()}") # Show current mode
        imgui.text("Right Click: Pan | Scroll: Zoom")
        imgui.end()

    def _render_inspector(self, region_int_id: Optional[int]):
        imgui.begin("Region Inspector")
        
        if region_int_id is not None:
            # Fetch data lazily
            state = self.net.get_state()
            regions = state.get_table("regions")
            
            try:
                row = regions.filter(pl.col("id") == region_int_id).row(0, named=True)
                
                imgui.text_colored((0, 1, 0, 1), f"{row.get('name', 'Unknown')}")
                imgui.text(f"ID: {region_int_id} | Hex: {row.get('hex', 'N/A')}")
                imgui.separator()
                imgui.text(f"Owner: {row.get('owner', 'None')}")
                imgui.text(f"Type:  {row.get('type', '-')}")
                
            except Exception:
                imgui.text_colored((1, 0, 0, 1), "Region Data Error")
        else:
            imgui.text_disabled("Select a region on map...")
            
        imgui.end()

    def _render_region_list(self):
        is_open = imgui.begin("All Regions", True)[1]
        self.show_region_list = is_open
        
        if is_open:
            state = self.net.get_state()
            regions = state.get_table("regions")
            limit = 200
            
            imgui.text_disabled(f"Showing first {limit} regions")
            
            for row in regions.head(limit).iter_rows(named=True):
                label = f"{row.get('name', '?')} ({row.get('hex', '?')})"
                if imgui.selectable(label)[0]:
                    if self.on_focus_request:
                        cx = row.get('center_x', 0)
                        cy = row.get('center_y', 0)
                        self.on_focus_request(cx, cy)
                        
        imgui.end()