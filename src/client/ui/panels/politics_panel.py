import polars as pl
from imgui_bundle import imgui
from src.client.ui.panels.base_panel import BasePanel # <--- New Import
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class PoliticsPanel(BasePanel):
    def __init__(self):
        # Configure default position/size here
        super().__init__("POLITICS", x=10, y=100, w=240, h=520)

    def _render_content(self, composer: UIComposer, state, **kwargs):
        player_tag = kwargs.get("player_tag", "")
        
        # --- 1. Fetch Data ---
        stability = 50.0
        corruption = 50.0
        approval = 50.0
        
        if "countries" in state.tables:
            try:
                df = state.tables["countries"]
                row = df.filter(pl.col("id") == player_tag)
                if not row.is_empty():
                    stability = float(row["gvt_stability"][0])
                    corruption = float(row["gvt_corruption"][0])
                    approval = float(row["gvt_approval"][0])
            except Exception:
                pass

        # --- 2. Render Widgets ---
        composer.draw_section_header("CONSTITUTIONAL FORM")
        imgui.text("Multi-party democracy")
        imgui.dummy((0, 5))

        # Ideology Slider
        composer.draw_section_header("IDEOLOGY", show_more_btn=False)
        imgui.push_style_color(imgui.Col_.slider_grab, GAMETHEME.col_active_accent)
        imgui.push_style_color(imgui.Col_.frame_bg, GAMETHEME.popup_bg)
        imgui.slider_float("##ideology", 0.5, 0.0, 1.0, "")
        imgui.pop_style_color(2)
        
        imgui.text_disabled("Left")
        imgui.same_line()
        imgui.set_cursor_pos_x(imgui.get_content_region_avail().x - 30)
        imgui.text_disabled("Right")
        
        imgui.dummy((0, 5))
        if imgui.button("INTERNAL LAWS", (imgui.get_content_region_avail().x, 0)):
            pass 
        imgui.dummy((0, 8))

        # Metrics
        composer.draw_section_header("APPROVAL", show_more_btn=False)
        col = GAMETHEME.col_positive if approval > 40 else GAMETHEME.col_negative
        composer.draw_meter("", approval, col) 

        composer.draw_section_header("STABILITY", show_more_btn=False)
        col = GAMETHEME.col_positive if stability > 50 else GAMETHEME.col_warning
        composer.draw_meter("", stability, col) 

        composer.draw_section_header("CORRUPTION", show_more_btn=False)
        col = GAMETHEME.col_negative if corruption > 30 else GAMETHEME.col_positive
        composer.draw_meter("", corruption, col) 
        
        imgui.dummy((0, 10))
        
        if imgui.button("TREATIES", (imgui.get_content_region_avail().x, 35)):
            pass