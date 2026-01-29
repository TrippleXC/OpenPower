import polars as pl
from imgui_bundle import imgui
from src.client.ui.panels.base_panel import BasePanel
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class EconomyPanel(BasePanel):
    def __init__(self):
        # We set a default X position (e.g., 1600) for the first launch.
        # ImGui will save the user's preferred position in the .ini file after that.
        super().__init__("ECONOMY", x=1600, y=100, w=260, h=450)

    def _render_content(self, composer: UIComposer, state, **kwargs):
        player_tag = kwargs.get("player_tag", "")

        # --- 1. Fetch Economy Data ---
        reserves = -25000000000 # Fallback
        gdp_per_capita = 0
        tax_rate = 0.2 # Default if missing
        
        if "countries" in state.tables:
            try:
                df = state.tables["countries"]
                row = df.filter(pl.col("id") == player_tag)
                if not row.is_empty():
                    reserves = int(row["money_reserves"][0])
                    gdp_per_capita = int(row["gdp_per_capita"][0])
                    tax_rate = float(row["global_tax_rate"][0])
            except Exception:
                pass

        # --- 2. Calculate Total GDP (Pop * Per Capita) ---
        total_pop = 0
        if "regions" in state.tables:
            try:
                df_pop = state.tables["regions"]
                # Sum population of all regions owned by player
                player_regions = df_pop.filter(pl.col("owner") == player_tag)
                if not player_regions.is_empty():
                    p14 = player_regions.select(pl.col("pop_14")).sum().item()
                    p1564 = player_regions.select(pl.col("pop_15_64")).sum().item()
                    p65 = player_regions.select(pl.col("pop_65")).sum().item()
                    total_pop = p14 + p1564 + p65
            except Exception:
                pass

        total_gdp = total_pop * gdp_per_capita
        
        # --- 3. Calculate Income ---
        # "Income must be tax rate of GDP"
        calculated_income = total_gdp * tax_rate

        # --- 4. Render UI ---
        
        # Economic Model Section
        composer.draw_section_header("ECONOMIC MODEL", show_more_btn=False)
        
        imgui.push_style_color(imgui.Col_.frame_bg, GAMETHEME.popup_bg)
        imgui.push_style_color(imgui.Col_.slider_grab, GAMETHEME.col_active_accent)
        
        # Placeholder slider for "State vs Free Market"
        imgui.slider_float("##eco_model", 0.2, 0.0, 1.0, "")
        imgui.pop_style_color(2)
        
        imgui.text_disabled("State-Controlled")
        imgui.same_line()
        imgui.set_cursor_pos_x(imgui.get_content_region_avail().x - 70)
        imgui.text_disabled("Free Market")
        imgui.dummy((0, 5))

        # GDP Section
        composer.draw_section_header(f"GDP: ${total_gdp:,.0f}")
        
        # Meter visual: Assume $1 Trillion is "max" for the bar logic, just for visualization
        gdp_health = min((total_gdp / 1000000000000) * 100, 100.0)
        composer.draw_meter("", gdp_health, GAMETHEME.col_positive) 
        
        imgui.text_disabled(f"Per Capita: ${gdp_per_capita:,}")
        imgui.dummy((0, 5))

        # Budget Section
        composer.draw_section_header("BUDGET")
        
        composer.draw_currency_row("INCOME", calculated_income)
        
        # Expenses remain a placeholder for now
        expenses = 0
        composer.draw_currency_row("EXPENSES", expenses)
        
        balance = calculated_income - expenses
        col_bal = GAMETHEME.col_negative if balance < 0 else GAMETHEME.col_positive
        composer.draw_currency_row("BALANCE", balance, col_bal)
        
        # Real Reserves from DB
        col_res = GAMETHEME.col_negative if reserves < 0 else GAMETHEME.col_positive
        composer.draw_currency_row("AVAILABLE", reserves, col_res)
        
        imgui.dummy((0, 8))

        # Resources Section
        composer.draw_section_header("RESOURCES")
        composer.draw_meter("", 66.0, GAMETHEME.col_positive)
        
        imgui.dummy((0, 15))
        
        # Footer
        imgui.button("TRADE", (-1, 35))