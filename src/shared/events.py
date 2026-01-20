from dataclasses import dataclass

@dataclass
class GameEvent:
    """
    Base class for all internal simulation events.
    
    Architecture Note:
        Events are distinct from Actions.
        - Actions: External commands FROM the user/network TO the engine.
        - Events: Internal signals FROM one system TO another.
        
        Using an Event Bus allows systems to be decoupled. For example, the 
        AudioSystem can listen for 'EventNewDay' to play a sound without 
        knowing anything about the TimeSystem.
    """
    pass

@dataclass
class EventNewDay(GameEvent):
    """
    Fired once when the date changes (at 00:00).
    Used by Economy (taxes), Population (growth), and Politics systems.
    """
    day: int
    month: int
    year: int

@dataclass
class EventNewHour(GameEvent):
    """
    Fired every in-game hour.
    Used for granular updates like day/night cycle lighting or military movement steps.
    """
    hour: int
    total_minutes: int
    
@dataclass
class EventRealSecond(GameEvent):
    """
    Fired once per real-world second (approx 1Hz).
    Used for pacing economy/resource ticks to avoid CPU spikes 
    while maintaining smooth progression.
    """
    game_seconds_passed: float  # How much in-game time happened in this real second?
    is_paused: bool