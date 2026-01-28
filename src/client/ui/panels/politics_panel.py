from imgui_bundle import imgui
import polars as pl
from src.client.ui.composer import UIComposer
from src.server.state import GameState
from src.client.ui.theme import GAMETHEME

class PoliticsPanel:
    def render(self, composer: UIComposer, state: GameState, player_tag: str, **kwargs):
        expanded, opened = composer.begin_panel("POLITICS", 10, 100, 240, 520, is_visible=True)
        
        # --- 1. Fetch Data ---
        stability = 50.0
        corruption = 50.0
        approval = 50.0
        
        if "countries" in state.tables:
            try:
                df = state.tables["countries"]
                # Filter for the current player
                row = df.filter(pl.col("id") == player_tag)
                if not row.is_empty():
                    # Extract values (assuming they are 0-100 integers in DB)
                    stability = float(row["gvt_stability"][0])
                    corruption = float(row["gvt_corruption"][0])
                    approval = float(row["gvt_approval"][0])
            except Exception as e:
                print(f"[PoliticsPanel] Data Fetch Error: {e}")

        if expanded:
            # 2. Constitutional Form
            composer.draw_section_header("CONSTITUTIONAL FORM")
            imgui.text("Multi-party democracy")
            imgui.dummy((0, 5))

            # 3. Ideology (Visual Only for now as it wasn't in schema)
            composer.draw_section_header("IDEOLOGY", show_more_btn=False)
            
            imgui.push_style_color(imgui.Col_.slider_grab, GAMETHEME.col_active_accent)
            imgui.push_style_color(imgui.Col_.frame_bg, GAMETHEME.popup_bg)
            
            # Using Approval as a proxy for 'Alignment' just to make it dynamic, 
            # or keep it static if you prefer.
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

            # 4. Real Metrics
            # We color code based on values
            composer.draw_section_header("APPROVAL", show_more_btn=False)
            col = GAMETHEME.col_positive if approval > 40 else GAMETHEME.col_negative
            composer.draw_meter("", approval, col) 

            # Pressure isn't in schema, leaving as calculation placeholder
            composer.draw_section_header("PRESSURE", show_more_btn=False)
            composer.draw_meter("", (100 - stability) * 0.5, GAMETHEME.col_negative) 

            composer.draw_section_header("STABILITY", show_more_btn=False)
            col = GAMETHEME.col_positive if stability > 50 else GAMETHEME.col_warning
            composer.draw_meter("", stability, col) 

            composer.draw_section_header("CORRUPTION", show_more_btn=False)
            # High corruption is bad (Red), low is good (Green)
            col = GAMETHEME.col_negative if corruption > 30 else GAMETHEME.col_positive
            composer.draw_meter("", corruption, col) 
            
            imgui.dummy((0, 10))
            
            if imgui.button("TREATIES", (imgui.get_content_region_avail().x, 35)):
                pass

        composer.end_panel()
        return opened