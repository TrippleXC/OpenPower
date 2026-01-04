from src.server.session import GameSession
from src.shared.actions import GameAction
from src.server.state import GameState

class NetworkClient:
    """
    The Bridge between the Client View (UI) and the Server Session.
    
    Architecture:
        Currently, this is a 'Mock' client that holds a direct reference 
        to the local GameSession instance.
        
        To add Multiplayer later:
        1. Create a 'RemoteNetworkClient' class.
        2. Replace 'self.session.receive_action()' with 'socket.send()'.
        3. The rest of the game code (Views, Renderers) won't notice the difference.
    """
    def __init__(self, session: GameSession):
        self.session = session
        self.player_id = "local_admin" # Default ID for single-player/editor

    def send_action(self, action: GameAction):
        """
        Sends an intent to the server.
        The client does NOT apply the action locally; it waits for the server to sync state.
        """
        # Ensure the action is tagged with our ID
        action.player_id = self.player_id
        self.session.receive_action(action)

    def get_state(self) -> GameState:
        """
        Fetches the latest world state for rendering.
        """
        return self.session.get_state_snapshot()

    def request_save(self):
        """
        Editor-specific command to save changes to disk.
        """
        print("[NetworkClient] Requesting server to save map data...")
        self.session.save_map_changes()