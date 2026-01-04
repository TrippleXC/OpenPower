from pathlib import Path
from typing import List

from src.server.state import GameState
from src.server.io.loader import DataLoader
from src.server.io.exporter import DataExporter
from src.engine.simulator import Engine
from src.shared.actions import GameAction

class GameSession:
    """
    The 'Host' of the game. It manages the lifecycle of the simulation.
    
    Responsibilities:
    1. Initialization: Loads data using DataLoader.
    2. Loop: Ticks the Engine with a delta_time.
    3. Networking: Receives actions from clients (even if local).
    4. Persistence: Handles saving/loading.
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        
        # 1. Initialize IO subsystems
        self.loader = DataLoader(root_dir)
        self.exporter = DataExporter(root_dir)
        
        # 2. Load the World
        # This creates the initial GameState from files.
        self.state: GameState = self.loader.load_initial_state()
        
        # 3. Action Queue
        # We buffer actions received from the network/UI and apply them
        # all at once during the next tick. This ensures thread safety.
        self.action_queue: List[GameAction] = []

    def tick(self, delta_time: float):
        """
        The heartbeat of the server. Called 60 times per second by the Main Loop.
        """
        if not self.action_queue and delta_time <= 0:
            return

        # Pass the queue to the Engine to process logic
        Engine.step(self.state, self.action_queue, delta_time)
        
        # Clear queue after processing
        self.action_queue.clear()

    def receive_action(self, action: GameAction):
        """
        Endpoint for Clients to submit commands.
        In the future, this will be connected to a TCP/UDP socket.
        """
        # TODO: Add validation here (e.g., "Is Player X allowed to move Unit Y?")
        self.action_queue.append(action)

    def get_state_snapshot(self) -> GameState:
        """
        Returns the data for rendering.
        
        Network Note:
            In a real network implementation, this would serialise 
            the GameState (or a delta) to Apache Arrow bytes.
            For local single-player, we just return the object reference (Zero-Copy).
        """
        return self.state

    def save_map_changes(self):
        """
        Special command for the Editor to force a disk write.
        """
        self.exporter.save_regions(self.state)