import polars as pl
from imgui_bundle import imgui
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME

class DemographicsPanel:
    def render(self, composer: UIComposer, state, player_tag: str, **kwargs):
        # Position: Left Side, offset below Politics
        expanded, opened = composer.begin_panel("DEMOGRAPHICS", 10, 350, 240, 480, is_visible=True)
        
        # --- 1. Aggregation Logic ---
        total_pop = 0
        pop_14 = 0
        pop_15_64 = 0
        pop_65 = 0
        
        # Data aggregation from regions belonging to the player
        if "regions" in state.tables:
            try:
                df = state.tables["regions"]
                # Schema says owner column is "_owner" in regions
                player_regions = df.filter(pl.col("owner") == player_tag)
                
                if not player_regions.is_empty():
                    pop_14 = player_regions.select(pl.col("pop_14")).sum().item()
                    pop_15_64 = player_regions.select(pl.col("pop_15_64")).sum().item()
                    pop_65 = player_regions.select(pl.col("pop_65")).sum().item()
                    total_pop = pop_14 + pop_15_64 + pop_65
            except Exception as e:
                # Fallback if column names mismatch (e.g. 'owner' vs '_owner')
                print(f"[Demographics] Error: {e}")

        # Calculate percentages
        pct_14 = (pop_14 / total_pop * 100) if total_pop > 0 else 0
        pct_15_64 = (pop_15_64 / total_pop * 100) if total_pop > 0 else 0
        pct_65 = (pop_65 / total_pop * 100) if total_pop > 0 else 0

        if expanded:
            # 2. TOTAL POPULATION SUMMARY
            composer.draw_section_header("POPULATION SUMMARY")

            imgui.text("Total:")
            imgui.same_line()
            imgui.set_cursor_pos_x(imgui.get_content_region_avail().x + 20 - imgui.calc_text_size(f"{total_pop:,}").x)
            imgui.text_colored(GAMETHEME.col_active_accent, f"{total_pop:,}")
            
            imgui.dummy((0, 5))

            # 3. AGE DISTRIBUTION
            composer.draw_section_header("AGE STRUCTURE", show_more_btn=False)
            
            # Using real percentages
            composer.draw_meter(f"Youth: {pop_14:,}", pct_14, (0.4, 0.7, 1.0, 1.0))
            composer.draw_meter(f"Working: {pop_15_64:,}", pct_15_64, (0.3, 0.8, 0.4, 1.0))
            composer.draw_meter(f"Elderly: {pop_65:,}", pct_65, (0.8, 0.4, 0.4, 1.0))

            # 4. SOCIAL METRICS (Human Dev from countries_dem)
            composer.draw_section_header("DEVELOPMENT")
            
            human_dev_index = 0
            if "countries_dem" in state.tables:
                try:
                    dem_df = state.tables["countries_dem"]
                    row = dem_df.filter(pl.col("id") == player_tag)
                    if not row.is_empty():
                        human_dev_index = row["human_dev"][0]
                except: pass

            composer.draw_meter("HDI Score", float(human_dev_index), GAMETHEME.col_info)
            
            imgui.dummy((0, 15))
            
            # 5. ACTION BUTTONS
            if imgui.button("MIGRATION POLICY", (-1, 30)):
                pass
            if imgui.button("SOCIAL PROGRAMS", (-1, 30)):
                pass

        composer.end_panel()
        return opened