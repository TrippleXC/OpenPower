import hashlib
import colorsys
from typing import Dict, Tuple

def generate_political_colors(owner_tags: list[str], salt: str = "seed1") -> Dict[str, Tuple[int, int, int]]:
    """
    Generates deterministic random colors for a list of tags.
    
    Args:
        owner_tags: List of strings (e.g., country codes).
        salt: Change this string to reshuffle all colors if you don't like the current palette.
    """
    color_map = {}
    
    for tag in owner_tags:
        if not tag or tag == "None":
            color_map[tag] = (0, 0, 0) # Black for null
            continue
        
        # 1. Combine tag with a salt to ensure uniqueness and allow reshuffling
        input_str = f"{tag}-{salt}"
        
        # 2. Get the MD5 hash (16 bytes)
        hash_bytes = hashlib.md5(input_str.encode('utf-8')).digest()
        
        # 3. Extract 3 distinct values from the hash to control H, S, and L
        # We use different byte slices so H, S, and L are independent
        h_int = int.from_bytes(hash_bytes[0:4], 'big')
        s_int = int.from_bytes(hash_bytes[4:8], 'big')
        l_int = int.from_bytes(hash_bytes[8:12], 'big')
        
        # 4. Calculate Hue (0.0 - 1.0)
        # The avalanche effect of MD5 ensures 'USA' and 'USB' have wildly different hues.
        hue = (h_int % 360) / 360.0
        
        # 5. Calculate Saturation (0.6 - 1.0)
        # Avoids 0.0-0.5 so colors don't look grey/washed out
        saturation = 0.6 + ((s_int % 40) / 100.0)
        
        # 6. Calculate Lightness (0.4 - 0.7)
        # Avoids 0.0-0.3 (too dark) and 0.8-1.0 (too white)
        lightness = 0.4 + ((l_int % 30) / 100.0)
        
        # 7. Convert HLS to RGB
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        
        color_map[tag] = (int(r * 255), int(g * 255), int(b * 255))
        
    return color_map