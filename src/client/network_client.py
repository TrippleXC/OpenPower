from src.server.session import GameSession
from src.shared.actions import GameAction
from src.server.state import GameState

class NetworkClient:
    """
    The Bridge between the Client View (UI) and the Server Session.
    
    Architecture (Service Pattern):
        This component isolates the 'Network' logic. 
        Currently, it mocks a network connection by holding a direct reference 
        to the local GameSession.
        
        Future Refactoring for Multiplayer:
        1. Create a `RemoteNetworkClient` implementing the same methods.
        2. Replace `self.session.receive_action()` with `socket.send()`.
        3. The Editor/GameView won't need any changes.
    """
    
    def __init__(self, session: GameSession):
        self.session = session
        # Default ID for single-player/editor mode.
        # In a real game, this would be assigned by the server upon handshake.
        self.player_id = "local_admin" 

    def send_action(self, action: GameAction):
        """
        Sends an intent to the server.
        
        Note: The client does NOT apply the action locally immediately.
        It waits for the server to process it and return the new state.
        This is 'Authoritative Server' architecture.
        """
        # Tag the action so the server knows who sent it
        action.player_id = self.player_id
        self.session.receive_action(action)

    def get_state(self) -> GameState:
        """
        Fetches the latest world state for rendering.
        """
        # In a real network scenario, this might return the last received snapshot
        # rather than querying the session directly.
        return self.session.get_state_snapshot()

    def request_save(self):
        """
        Editor-specific command to flush changes to disk.
        """
        print("[NetworkClient] Requesting server to save map data...")
        self.session.save_map_changes()