import polars as pl
from typing import Dict, Tuple
from src.server.state import GameState
from src.client.map_modes.base_map_mode import BaseMapMode
from src.client.utils.gradient import lerp_color

class GradientMapMode(BaseMapMode):
    """
    Generic mode for visualizing numeric data on a gradient (Blue -> Red).
    Can target columns in 'regions' table OR 'countries' table.
    """
    def __init__(self, mode_name: str, column_name: str, fallback_to_country: bool = True):
        self._name = mode_name
        self.column_name = column_name
        self.fallback_to_country = fallback_to_country
        
        self.col_min = (0, 0, 255) # Blue (Low)
        self.col_max = (255, 0, 0) # Red (High)
        self.col_none = (40, 40, 40) # Grey (No Data)

    @property
    def name(self) -> str:
        return self._name

    def calculate_colors(self, state: GameState) -> Dict[int, Tuple[int, int, int]]:
        if "regions" not in state.tables: return {}
        
        regions_df = state.get_table("regions")
        target_df = regions_df
        target_col = self.column_name
        
        # 1. Data Resolution Strategy
        # Check if the column is directly on the region (e.g., local population)
        if target_col in regions_df.columns:
            work_df = regions_df.select(["id", target_col])
        
        # If not, and fallback enabled, try to join with countries (e.g., GDP per capita)
        elif self.fallback_to_country and "countries" in state.tables:
            countries_df = state.get_table("countries")
            
            if target_col in countries_df.columns:
                # Join Regions with Countries on 'owner'
                # We perform a left join to keep all regions even if owner is missing
                work_df = regions_df.join(
                    countries_df, 
                    left_on="owner", 
                    right_on="id", 
                    how="left"
                ).select(["id", target_col])
            else:
                return {} # Column not found anywhere
        else:
            return {}

        # 2. Statistics for Gradient
        # Filter nulls to find min/max
        valid_data = work_df.select(pl.col(target_col)).drop_nulls()
        if valid_data.is_empty():
            return {}

        min_val = valid_data.min().item()
        max_val = valid_data.max().item()

        # Avoid division by zero
        if max_val == min_val:
            max_val = min_val + 1.0

        # 3. Generate Colors
        # Iterate and build dict (Optimization: This loop is O(N_Regions), reasonably fast for <50k)
        result = {}
        for row in work_df.iter_rows(named=True):
            rid = row["id"]
            val = row[target_col]
            
            if val is None:
                result[rid] = self.col_none
            else:
                result[rid] = lerp_color(float(val), float(min_val), float(max_val), self.col_min, self.col_max)
                
        return result