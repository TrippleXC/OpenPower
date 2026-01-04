from typing import List
import polars as pl

from src.server.state import GameState
from src.shared.actions import GameAction, ActionSetRegionOwner, ActionSetTax
from src.engine.systems import territory, economy

class Engine:
    """
    The deterministic core of the OpenPower simulation.
    
    Design Philosophy:
        The Engine is 'Functional' in nature.
        Input: State + Actions + Time
        Output: New State
        
        It is completely decoupled from the Client, Server, or Network. 
        This allows us to run this logic on a headless Linux server 
        or inside a local Pytest suite with zero changes.
    """

    @staticmethod
    def step(state: GameState, actions: List[GameAction], delta_time: float):
        """
        Advances the simulation by one 'Tick'.
        
        Args:
            state: The mutable GameState container holding all dataframes.
            actions: A list of Player/AI commands to process this tick.
            delta_time: Time elapsed in seconds (used for movement, production progress).
        """
        
        # 1. Process Discrete Actions (Command Pattern)
        # Actions are processed sequentially. This ensures determinism:
        # if Player A captures a region and Player B nukes it in the same tick,
        # the order in the list determines the outcome.
        for action in actions:
            Engine._apply_action(state, action)
            
        # 2. Continuous Simulation (Systems)
        # Here we would call systems that run every frame/tick, regardless of user input.
        # Examples: Unit movement, factory production, population growth.
        # economy.calculate_daily_income(state) # Uncomment when implemented
        
        # 3. Update Meta-State
        # Increment the internal clock.
        state.globals["tick"] += 1

    @staticmethod
    def _apply_action(state: GameState, action: GameAction):
        """
        Routes a generic GameAction to the specific system logic.
        Uses Python 3.10+ Structural Pattern Matching for readable control flow.
        """
        match action:
            # --- Map / Territory Logic ---
            case ActionSetRegionOwner(player_id, region_id, new_owner_tag):
                # In the future, we can add a check here:
                # if logic.can_modify_map(player_id): ...
                territory.apply_region_ownership_change(state, region_id, new_owner_tag)

            # --- Economy / Political Logic ---
            case ActionSetTax(player_id, country_tag, new_rate):
                economy.apply_tax_change(state, country_tag, new_rate)
            
            # --- Fallback ---
            case _:
                # This catches any action types defined in shared/actions.py 
                # but not yet implemented in the Engine.
                print(f"[Engine] WARNING: Received unhandled action type: {type(action).__name__}")