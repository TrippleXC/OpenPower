from imgui_bundle import imgui
import polars as pl
from typing import Optional, Callable
from src.server.state import GameState
from src.client.ui.theme import GAMETHEME

class RegionInspectorPanel:
    def __init__(self):
        self.filter_text: str = ""
        self._cached_list: list = []
        self._cache_dirty = True

    def render(self, composer, state: GameState, **kwargs) -> bool:
        """
        Renders the detailed view of a selected region.
        The selected_region_id and callback are pulled from kwargs to maintain
        a flexible, modular interface.
        """
        # Data extraction from shared context
        region_id = kwargs.get("selected_region_id")
        on_focus_request = kwargs.get("on_focus_request")

        # Position is handled by ImGui Cond_.first_use_ever in composer
        expanded, opened = composer.begin_panel("Region Inspector", 400, 200, 300, 480, is_visible=True)

        if expanded:
            if region_id is None:
                imgui.text_disabled("Select a region on the map\nto view its statistics.")
            else:
                self._render_details(region_id, state, on_focus_request)

        composer.end_panel()
        # Return False if 'X' was clicked to let the Layout hide this panel
        return opened

    def _render_details(self, region_id, state, on_focus_request):
        """Internal helper to keep the render flow clean."""
        try:
            regions = state.get_table("regions")
            row_df = regions.filter(pl.col("id") == region_id)
            
            if row_df.is_empty():
                imgui.text_colored(GAMETHEME.col_error, "Region not found in database.")
                return

            row = row_df.row(0, named=True)
            imgui.text_colored(GAMETHEME.col_active_accent, f"NAME: {row.get('name', '???')}")
            
            if on_focus_request and imgui.button("CENTER CAMERA"):
                on_focus_request(region_id, float(row.get('center_x', 0)), float(row.get('center_y', 0)))

            imgui.separator()
            imgui.text(f"Owner: {row.get('owner', 'Neutral')}")
            imgui.text(f"Biome: {row.get('biome', 'N/A')}")
            
            pop = row.get('pop_14', 0) + row.get('pop_15_64', 0) + row.get('pop_65', 0)
            imgui.text(f"Total Population: {pop:,}")
            
        except Exception as e:
            imgui.text_disabled(f"Error loading data: {e}")

    def _update_filter_cache(self, state: GameState, filter_text: str):
        """Rebuilds the UI list from the dataframe."""
        try:
            if "regions" not in state.tables: return

            df = state.tables["regions"]
            txt = filter_text.lower()
            
            cols = ["id", "name", "owner", "center_x", "center_y"]

            if not txt:
                res = df.select(cols).sort("name").head(50)
            else:
                res = df.filter(
                    pl.col("name").str.to_lowercase().str.contains(txt) | 
                    pl.col("owner").str.to_lowercase().str.contains(txt)
                ).select(cols).head(50)

            self._cached_list = res.rows()
            self._cache_dirty = False
            
        except Exception as e:
            print(f"[RegionInspector] Filter Error: {e}")
            self._cached_list = []