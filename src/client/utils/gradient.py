import math

def lerp_color(val: float, min_val: float, max_val: float, 
               start_color: tuple[int, int, int], 
               end_color: tuple[int, int, int]) -> tuple[int, int, int]:
    """
    Linear Interpolation between two RGB colors based on a value.
    """
    if max_val == min_val:
        return start_color
        
    t = (val - min_val) / (max_val - min_val)
    t = max(0.0, min(1.0, t)) # Clamp 0..1
    
    r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
    g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
    b = int(start_color[2] + (end_color[2] - start_color[2]) * t)
    
    return (r, g, b)

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4)) # type: ignore