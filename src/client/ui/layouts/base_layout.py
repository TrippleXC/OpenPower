import arcade
from typing import Optional, Any, Dict
from src.client.services.network_client_service import NetworkClient
from src.client.ui.panels.region_inspector import RegionInspectorPanel
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from imgui_bundle import imgui

class BaseLayout:
    """
    BaseLayout serves as the foundation for all user interface layouts in the application.
    
    It manages shared UI components that persist across different game states (like 
    the Editor or Live Game) and acts as a bridge between the UI event system 
    and the Viewport/Camera controllers.
    
    Attributes:
        net (NetworkClient): Service for fetching game state and sending commands.
        viewport_ctrl (ViewportController): The controller handling map logic and camera.
        composer (UIComposer): Manages the visual theme and UI element styling.
        inspector (RegionInspectorPanel): The UI panel for viewing specific region details.
    """

    def __init__(self, net_client: NetworkClient, viewport_ctrl: Any):
        """
        Initializes the shared UI infrastructure.

        Args:
            net_client: Instance of the NetworkClient service.
            viewport_ctrl: The controller for the map viewport (ViewportController).
        """
        self.net = net_client
        self.viewport_ctrl = viewport_ctrl
        
        # UIComposer handles theme application (colors, fonts, padding)
        # using the global GAMETHEME configuration.
        self.composer = UIComposer(GAMETHEME)
        
        # Store references to dynamically created panels if needed
        self.panels: Dict[str, Dict[str, Any]] = {}

        # PERSISTENT UI STATE:
        # We store the region ID at the moment of the right-click to prevent 
        # the menu from updating its content as the mouse moves.
        self._menu_hit_id: Optional[int] = None

        # Instantiate the Inspector Panel once. 
        # This allows the panel to maintain its internal state (like scroll position 
        # or cached layout data) even when the selected region changes.
        self.register_panel("INSPECTOR", RegionInspectorPanel(), visible=False)

    def register_panel(self, panel_id: str, instance: Any, visible: bool = True, **metadata):
        """Registers a panel for automatic rendering and management."""
        self.panels[panel_id] = {
            "instance": instance,
            "visible": visible,
            **metadata
        }
    
    def _render_panels(self, state: Any, **extra_ctx):
        """
        Iterates through all registered panels and renders them if visible.
        Handles the 'closed' signal from ImGui automatically.
        """
        for panel_id, data in self.panels.items():
            if not data["visible"]:
                continue

            # Composition: We delegate the actual UI drawing to the panel instance
            # Most panels need (composer, state), some need extra context (like player_tag)
            panel_instance = data["instance"]
            
            # Pass composer and state as base requirements, merge with extra context
            still_open = panel_instance.render(self.composer, state, **extra_ctx)

            # If the panel returns False (user clicked 'X'), we hide it
            if still_open is False:
                data["visible"] = False

    def _render_context_menu(self, current_hovered_id: Optional[int]):
        """
        Renders the right-click menu. 
        Captures the 'current_hovered_id' only at the moment of the click 
        to 'lock' the menu to the target region.
        """
        # Step 1: Capture the state exactly when the click is released
        if self.composer.is_background_clicked():
            # "Freeze" the ID for the duration of this popup session
            self._menu_hit_id = current_hovered_id
            self.composer.open_popup("global_map_context")

        # 

        # Step 2: Use the frozen ID inside the popup
        if self.composer.begin_popup("global_map_context"):
            
            # We reference self._menu_hit_id instead of the dynamic argument
            target_id = self._menu_hit_id

            if target_id is not None:
                imgui.text_disabled(f"Target: Region #{target_id}")
                
                if self.composer.draw_menu_item("View Details", "I"):
                    self.panels["INSPECTOR"]["visible"] = True
                    # Force selection to sync visuals with the inspected region
                    self.viewport_ctrl.select_region_by_id(target_id)
                
                if self.composer.draw_menu_item("Jump to Camera"):
                    self.viewport_ctrl.focus_on_region(target_id)
                
                imgui.separator()

            if self.composer.begin_menu("Map Mode"):
                if self.composer.draw_menu_item("Political"):
                    if hasattr(self, 'map_mode'): setattr(self, 'map_mode', "political")
                if self.composer.draw_menu_item("Terrain"):
                    if hasattr(self, 'map_mode'): setattr(self, 'map_mode', "terrain")
                self.composer.end_menu()

            imgui.separator()
            if self.composer.draw_menu_item("Close All Panels"):
                for p in self.panels.values(): p["visible"] = False

            self.composer.end_popup()
        else:
            # Optional: Clear the hit ID when the popup is closed
            # to avoid stale data on the next frame.
            pass

    def is_panel_visible(self, panel_id: str) -> bool:
        return self.panels.get(panel_id, {}).get("visible", False)

    def toggle_panel(self, panel_id: str):
        if panel_id in self.panels:
            self.panels[panel_id]["visible"] = not self.panels[panel_id]["visible"]

    def _on_focus_region(self, region_id: int, image_x: float, image_y: float):
        """
        Internal callback triggered when the user clicks 'Focus' in the UI.
        
        This method delegates the coordinate conversion and camera movement 
        to the ViewportController. 

        Args:
            region_id: The unique ID of the region to center on.
            image_x: Raw X coordinate on the map texture (unused here, handled by controller).
            image_y: Raw Y coordinate on the map texture (unused here, handled by controller).
        """
        # DELEGATION: We tell the controller WHICH region to focus on.
        # The controller is responsible for:
        # 1. Looking up the region's center in the data tables.
        # 2. Converting those coordinates to world space.
        # 3. Moving the camera and syncing it with the Arcade engine.
        self.viewport_ctrl.focus_on_region(region_id)