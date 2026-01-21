import time
import polars as pl
from dataclasses import dataclass
from typing import Optional

from src.shared.config import GameConfig
from src.server.session import GameSession
from src.client.utils.coords_util import calculate_centroid

@dataclass
class NewGameContext:
    session: GameSession
    player_tag: str
    start_pos: Optional[tuple[float, float]]

class NewGameTask:
    def __init__(self, session: GameSession, config: GameConfig, player_tag: str):
        self.session = session
        self.config = config
        self.player_tag = player_tag
        
        # LoadingTask Protocol
        self.progress: float = 0.0
        self.status_text: str = "Preparing Campaign..."

    def run(self) -> NewGameContext:
        # 1. Visual Feedback
        self.status_text = f"Initializing {self.player_tag}..."
        self.progress = 0.2
        time.sleep(0.2) # Small delay so user sees the screen change

        # 2. Heavy Math (Centroid Calculation)
        self.status_text = "Calculing capital location..."
        self.progress = 0.5
        
        state = self.session.get_state_snapshot()
        start_pos = None
        
        try:
            if "regions" in state.tables:
                df = state.tables["regions"]
                # Filter locally to find center
                owned_regions = df.filter(pl.col("owner") == self.player_tag)
                map_height = self.session.map_data.height
                start_pos = calculate_centroid(owned_regions, map_height)
        except Exception as e:
            print(f"[NewGameTask] Error: {e}")

        self.progress = 1.0
        return NewGameContext(self.session, self.player_tag, start_pos)