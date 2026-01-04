import polars as pl
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class GameState:
    """
    The central data store for the entire simulation, strictly adhering to Data-Oriented Design.
    
    Contrast with OOP:
        Instead of a 'Country' class containing a list of 'Region' objects,
        we hold flat tables (DataFrames). Relationships are defined by ID columns
        (e.g., 'owner_id' in the 'regions' table) and resolved via joins during logic processing.
    
    Benefits:
        1. Performance: Allows SIMD vectorization and cache-friendly processing via Polars.
        2. Moddability: Mods can add columns to tables without breaking class structures.
        3. Serialization: The entire state can be dumped to Arrow/Parquet instantly.
    """
    
    # Stores the primary game data.
    # Keys are table names (e.g., 'regions', 'countries').
    # Values are Polars DataFrames optimized for columnar access.
    tables: Dict[str, pl.DataFrame] = field(default_factory=dict)
    
    # Holds global simulation variables that don't fit into tables.
    # Used for time tracking, game speed, and global event flags.
    globals: Dict[str, Any] = field(default_factory=lambda: {
        "tick": 0,
        "date_str": "2001-01-01",
        "game_speed": 1.0
    })

    def get_table(self, name: str) -> pl.DataFrame:
        """
        Retrieves a reference to a simulation table.
        Raises KeyError if the table is missing to prevent silent logic failures.
        """
        if name not in self.tables:
            raise KeyError(f"Table '{name}' not found in GameState. Ensure Loader has initialized it.")
        return self.tables[name]

    def update_table(self, name: str, df: pl.DataFrame):
        """
        Replaces a table in the state.
        
        Note:
            In Polars, DataFrames are immutable. 'Updating' a table actually means
            replacing the reference with a new DataFrame. This is efficient because
            Polars uses Copy-on-Write (CoW) under the hood.
        """
        self.tables[name] = df