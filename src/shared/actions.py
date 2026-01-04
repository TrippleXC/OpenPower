from dataclasses import dataclass
from typing import Optional

# We use dataclasses here because they provide a concise way to define 
# data structures that are immutable by convention and easy to serialize 
# (e.g., to JSON or binary for networking later).
@dataclass
class GameAction:
    """
    Base class for all discrete game actions following the Command Pattern.
    
    Architecture Note:
        In this Data-Oriented architecture, Clients do not modify the GameState directly.
        Instead, they issue Actions. The Engine then processes these Actions deterministically.
        This approach simplifies:
        1. Networking (sending actions instead of full state).
        2. Undo/Redo systems (reverting an action).
        3. Replay systems (re-running a list of actions).
    """
    # Identifies who initiated the action ('local_player', 'server', or a specific player ID).
    # Essential for validation and multiplayer synchronization.
    player_id: str

# --- Map Actions ---

@dataclass
class ActionSetRegionOwner(GameAction):
    """
    Transfers ownership of a specific region to a new country.
    Used by the Editor (painting) and Gameplay (conquest/diplomacy).
    """
    region_id: int
    new_owner_tag: str

# --- Economy Actions ---

@dataclass
class ActionSetTax(GameAction):
    """
    Updates the tax rate for a specific country.
    """
    country_tag: str
    new_tax_rate: float