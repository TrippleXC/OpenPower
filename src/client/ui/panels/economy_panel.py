import polars as pl
from imgui_bundle import imgui
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class EconomyPanel:
    def render(self, composer: UIComposer, state, player_tag: str, **kwargs):
        # Position: Right Side
        vp_w = imgui.get_main_viewport().size.x
        expanded, opened = composer.begin_panel("ECONOMY", vp_w - 280, 100, 260, 450, is_visible=True)
        
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

        if expanded:
            # 1. Economic Model
            composer.draw_section_header("ECONOMIC MODEL", show_more_btn=False)
            
            imgui.push_style_color(imgui.Col_.frame_bg, GAMETHEME.popup_bg)
            imgui.push_style_color(imgui.Col_.slider_grab, GAMETHEME.col_active_accent)
            
            # Original placeholder slider for "State vs Free Market"
            imgui.slider_float("##eco_model", 0.2, 0.0, 1.0, "")
            imgui.pop_style_color(2)
            
            imgui.text_disabled("State-Controlled")
            imgui.same_line()
            imgui.set_cursor_pos_x(imgui.get_content_region_avail().x - 70)
            imgui.text_disabled("Free Market")
            imgui.dummy((0, 5))

            # 2. Economic Health (Showing Total GDP)
            # We format trillions/billions nicely
            composer.draw_section_header(f"GDP: ${total_gdp:,.0f}")
            
            # Meter visual: Assume $1 Trillion is "max" for the bar logic, just for visualization
            gdp_health = min((total_gdp / 1000000000000) * 100, 100.0)
            composer.draw_meter("", gdp_health, GAMETHEME.col_positive) 
            
            # Small detail text for per capita
            imgui.text_disabled(f"Per Capita: ${gdp_per_capita:,}")
            imgui.dummy((0, 5))

            # 3. Budget Section
            composer.draw_section_header("BUDGET")
            
            # Income is now dynamic based on your formula
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

            # 4. Resources
            composer.draw_section_header("RESOURCES")
            composer.draw_meter("", 66.0, GAMETHEME.col_positive)
            
            imgui.dummy((0, 15))
            
            # Footer
            imgui.button("TRADE", (-1, 35))

        composer.end_panel()
        return opened