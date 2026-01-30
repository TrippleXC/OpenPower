import math

def lerp_color(val: float, min_val: float, max_val: float, 
               start_color: tuple[int, int, int], 
               end_color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Linear Interpolation between two colors."""
    if max_val == min_val: return start_color
    t = (val - min_val) / (max_val - min_val)
    t = max(0.0, min(1.0, t))
    
    return (
        int(start_color[0] + (end_color[0] - start_color[0]) * t),
        int(start_color[1] + (end_color[1] - start_color[1]) * t),
        int(start_color[2] + (end_color[2] - start_color[2]) * t)
    )

def get_heatmap_color(t: float) -> tuple[int, int, int]:
    """
    Returns a color from a multi-stop gradient based on t (0.0 to 1.0).
    Blue -> Cyan -> Green -> Yellow -> Red
    """
    t = max(0.0, min(1.0, t))
    
    # Define stops: (Position, (R, G, B))
    stops = [
        (0.00, (0, 0, 255)),    # Blue (Low)
        (0.25, (0, 255, 255)),  # Cyan
        (0.50, (0, 255, 0)),    # Green (Mid)
        (0.75, (255, 255, 0)),  # Yellow
        (1.00, (255, 0, 0)),    # Red (High)
    ]
    
    # Find which two stops 't' falls between
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i+1]
        
        if t0 <= t <= t1:
            # Re-normalize t to 0..1 range within this segment
            local_t = (t - t0) / (t1 - t0)
            return lerp_color(local_t, 0, 1, c0, c1)
            
    return stops[-1][1]