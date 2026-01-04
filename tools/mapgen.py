"""
Map & Database Generator.

Architecture: "Color-As-ID"
----------------------------
1. Visual Map: Pixels represent region IDs.
2. Database: Maps HEX colors (Visual IDs) to Game Data.

Features:
- **Micro-Nation Merging**: Automatically fuses tiny subdivisions (e.g., Liechtenstein's 11 communes)
  into single regions to prevent pixel collisions and improve gameplay UX.
- **Data**: Extracts ISO codes, names, and calculates real surface area (km²).
- **TSV Export**: Uses Tab-Separated Values for robust string handling.
- **Smart Rescue**: Uses a spiral search algorithm with collision protection to ensure 
  tiny islands are not overwritten by neighbors.
- **Verification**: Mathematically proves map integrity before finishing.

Dependencies:
    pip install geopandas pandas rasterio numpy opencv-python unidecode pyproj
"""

import os
import sys
import csv
import random
import geopandas as gpd
import pandas as pd
from rasterio import features
from rasterio.transform import from_bounds, rowcol
import numpy as np
import cv2
from unidecode import unidecode

# === CONFIGURATION ===
CONFIG = {
    # Input source (Requires .shp, .shx, .dbf)
    "input_shp": "temp/regions.shp",
    
    # Outputs
    "output_png": "temp/regions.png",
    "output_tsv": "temp/regions.tsv",
    
    # Texture Resolution (10k is standard for detailed HOI4-style maps)
    "width": 10000,
    "height": 5000,
    
    # WGS84 Global Bounds
    "bounds": (-180.0, -90.0, 180.0, 90.0),
    
    # ID 0 is strictly reserved for Ocean/Background
    "background_id": 0,
    
    # List of Country Codes (ISO A3) to force-merge into single regions.
    # Why: In a global strategy game, having 11 tiny provinces for Liechtenstein 
    # causes rendering errors and makes clicking impossible.
    "merge_list": [
        "LIE", # Liechtenstein
        "SMR", # San Marino
        "VAT", # Vatican
        "MCO", # Monaco
        "AND", # Andorra
        "TUV", # Tuvalu
        "NRU"  # Nauru
    ]
}

def generate_random_colors(count):
    """
    Generates unique random RGB tuples.
    
    Why:
        Random colors are essential for modding. Mathematical sequential IDs 
        (like #000001, #000002) are visually indistinguishable to humans.
        Random colors allow modders to pick regions easily in Paint.NET.
    """
    print(f"Generating {count} unique visual colors...")
    colors = set()
    result_list = []
    
    while len(result_list) < count:
        r = random.randint(10, 255)
        g = random.randint(10, 255)
        b = random.randint(10, 255)
        color = (r, g, b)
        
        # Ensure we never generate Black (0,0,0) or duplicates
        if color not in colors and color != (0, 0, 0):
            colors.add(color)
            result_list.append(color)
            
    return result_list

def rgb_to_hex(r, g, b):
    """Converts RGB tuple to standard HEX string #RRGGBB."""
    return f"#{r:02X}{g:02X}{b:02X}"

def sanitize_text(text):
    """
    Sanitizes string data for game engine compatibility.
    
    1. Fixes 'Mojibake' (Windows CP1252 vs UTF-8 encoding errors).
    2. Transliterates to ASCII (removes diacritics) using unidecode.
    """
    if not isinstance(text, str):
        return ""
    
    # Step 1: Attempt to fix common Windows encoding corruption
    try:
        fixed_text = text.encode('cp1252').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        fixed_text = text

    # Step 2: Enforce ASCII (e.g., "München" -> "Munchen")
    return unidecode(fixed_text).strip()

def merge_micro_nations(gdf, codes_to_merge):
    """
    Combines all regions of specific countries into a single geometry.
    
    Why:
        Fixes the "Liechtenstein Paradox" where excessive administrative divisions
        in micro-nations are smaller than 1 pixel, causing validation failures.
    """
    print(f"Optimizing: Merging micro-nations {codes_to_merge}...")
    
    for code in codes_to_merge:
        # Filter rows belonging to this country
        subset = gdf[gdf['adm0_a3'] == code]
        
        if subset.empty or len(subset) <= 1:
            continue # Skip if country missing or already has only 1 region
            
        print(f"  -> Merging {len(subset)} regions for {code}...")
        
        # 1. Fuse geometries into one polygon (Union)
        # unary_union is efficient and handles MultiPolygons correctly
        unified_geom = subset.geometry.unary_union
        
        # 2. Create a representative row
        # We take metadata from the first region, but overwrite Name and Type
        new_row = subset.iloc[0].copy()
        new_row['geometry'] = unified_geom
        
        # Get country name (fallback to code if name missing)
        c_name = subset.iloc[0].get('admin', code) 
        new_row['name'] = c_name
        new_row['name_en'] = c_name
        new_row['type_en'] = "Sovereign State" # Reset local admin type
        
        # 3. Remove old rows from main DataFrame
        gdf = gdf[gdf['adm0_a3'] != code]
        
        # 4. Append new unified row
        # We must create a temporary GeoDataFrame to concatenate safely
        new_gdf = gpd.GeoDataFrame([new_row], crs=gdf.crs)
        gdf = pd.concat([gdf, new_gdf], ignore_index=True)
        
    return gdf

def main():
    print(f"--- Starting Ultimate Map Generation ---")

    # 1. Input Validation
    if not os.path.exists(CONFIG["input_shp"]):
        print(f"ERROR: Input file {CONFIG['input_shp']} not found.")
        sys.exit(1)

    print("Reading Shapefile (Forcing UTF-8)...")
    # GeoPandas often defaults to system encoding (CP1252 on Windows).
    try:
        gdf = gpd.read_file(CONFIG["input_shp"], encoding='utf-8')
    except Exception:
        print("Warning: Forced UTF-8 failed. Reverting to auto-detect.")
        gdf = gpd.read_file(CONFIG["input_shp"])

    # 2. Optimization: Merge Micro-Nations
    # This modifies the geometry before any processing happens.
    gdf = merge_micro_nations(gdf, CONFIG['merge_list'])

    total_regions = len(gdf)

    # 3. Physics Calculation: Real Area (km²)
    print("Calculating real surface area (reprojecting to metric)...")
    
    # Why: WGS84 (degrees) distorts size near poles.
    # We reproject to 'Cylindrical Equal Area' to get fair gameplay values.
    gdf_metric = gdf.to_crs({'proj': 'cea'})
    
    # Convert m² to km²
    gdf['area_km2'] = (gdf_metric.geometry.area / 1e6).astype(int)

    # 4. ID and Color Assignment
    # We assign a temporary integer ID (1..N) to handle rasterization cleanly.
    gdf['temp_id'] = range(1, total_regions + 1)
    
    random_colors = generate_random_colors(total_regions)
    id_to_color_map = {i + 1: color for i, color in enumerate(random_colors)}

    transform = from_bounds(*CONFIG['bounds'], CONFIG['width'], CONFIG['height'])

    # 5. Metadata Extraction & TSV Export
    print("Processing metadata...")
    
    tsv_rows = []
    # Rich header for gameplay logic
    tsv_header = [
        "hex", "name", "owner", "iso_region", "type", 
        "macro_region", "postal", "area_km2", "center_x", "center_y"
    ]
    tsv_rows.append(tsv_header)
    
    center_lookup = {}
    
    for _, row in gdf.iterrows():
        t_id = int(row['temp_id'])
        r, g, b = id_to_color_map[t_id]
        
        # Calculate pixel centroid for camera focus
        geom = row.geometry
        center_geo = geom.centroid
        c_row, c_col = rowcol(transform, center_geo.x, center_geo.y)
        c_x = int(max(0, min(c_col, CONFIG['width'] - 1)))
        c_y = int(max(0, min(c_row, CONFIG['height'] - 1)))

        # Metadata extraction logic
        raw_name = row.get('name', 'Unknown')
        name_en = row.get('name_en', None)
        
        # Prefer English name, fallback to Local name
        if name_en and isinstance(name_en, str) and len(name_en) > 1:
            display_name = sanitize_text(name_en)
        else:
            display_name = sanitize_text(raw_name)
            
        owner_code = row.get('adm0_a3', 'UNK').replace('-99', 'UNK')
        iso_reg = row.get('iso_3166_2', 'UNK') if isinstance(row.get('iso_3166_2'), str) else "UNK"
        admin_type = sanitize_text(row.get('type_en', 'Region'))
        macro_reg = sanitize_text(row.get('region', ''))
        postal = sanitize_text(row.get('postal', ''))
        area = int(row['area_km2'])

        # UX: Use HEX strings so modders can copy-paste from Photoshop
        hex_color = rgb_to_hex(r, g, b)
        
        tsv_rows.append([
            hex_color, display_name, owner_code, iso_reg, 
            admin_type, macro_reg, postal, area, c_x, c_y
        ])
        
        center_lookup[t_id] = (c_x, c_y)

    print(f"Saving Database: {CONFIG['output_tsv']}...")
    with open(CONFIG["output_tsv"], "w", encoding="utf-8-sig", newline='') as f:
        # Delimiter '\t' makes it a TSV file
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(tsv_rows)

    # 6. Rasterization
    print("Rasterizing geometry...")
    shapes = ((geom, value) for geom, value in zip(gdf.geometry, gdf['temp_id']))
    
    raster_ids = features.rasterize(
        shapes=shapes,
        out_shape=(CONFIG['height'], CONFIG['width']),
        transform=transform,
        fill=CONFIG['background_id'],
        dtype=np.uint32,
        all_touched=False # Clean borders
    )

    # 7. Rescue Logic (Smart Spiral with Collision Protection)
    print("Rescuing small regions (Smart Spiral)...")
    
    # Identify which regions failed to render
    present_ids = np.unique(raster_ids)
    missing_ids = np.setdiff1d(gdf['temp_id'].values, present_ids)
    
    if len(missing_ids) > 0:
        print(f"  -> Attempting to rescue {len(missing_ids)} regions...")
        
        # We must protect these missing IDs from overwriting EACH OTHER.
        protected_ids = set(missing_ids)
        placed_count = 0
        
        # Generator for spiral coordinates
        def get_spiral(start_x, start_y, max_r):
            yield start_x, start_y
            for r in range(1, max_r + 1):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if abs(dx) == r or abs(dy) == r:
                            yield start_x + dx, start_y + dy

        for m_id in missing_ids:
            if m_id not in center_lookup:
                continue
            
            c_x, c_y = center_lookup[m_id]
            best_candidate = None
            
            # Increase radius to 30 to account for merged micro-nations if they are still small
            for try_x, try_y in get_spiral(c_x, c_y, 30):
                if not (0 <= try_x < CONFIG['width'] and 0 <= try_y < CONFIG['height']):
                    continue
                
                current_pixel_val = raster_ids[try_y, try_x]
                
                # Priority 1: Water
                if current_pixel_val == CONFIG['background_id']:
                    best_candidate = (try_x, try_y)
                    break 
                
                # Priority 2: Land (not protected)
                if current_pixel_val not in protected_ids:
                    if best_candidate is None:
                        best_candidate = (try_x, try_y)
            
            if best_candidate:
                final_x, final_y = best_candidate
                raster_ids[final_y, final_x] = m_id
                placed_count += 1
            else:
                print(f"CRITICAL: No space found for ID {m_id} near {c_x},{c_y}")

        print(f"  -> Rescue operation finished. Placed {placed_count}/{len(missing_ids)}.")

    # 8. Integrity Verification
    print("--- Verifying Integrity ---")
    final_present_ids = np.unique(raster_ids)
    expected_set = set(gdf['temp_id'].values)
    found_set = set(final_present_ids)
    lost_regions = expected_set - found_set
    
    if len(lost_regions) == 0:
        print("SUCCESS: 100% Integrity. All regions are present on the map.")
    else:
        print(f"WARNING: Verification FAILED. {len(lost_regions)} regions are missing!")
        print("\n--- MISSING REGIONS REPORT ---")
        missing_info = gdf[gdf['temp_id'].isin(lost_regions)]
        for _, row in missing_info.iterrows():
            r_name = row.get('name_en', row.get('name', 'Unknown'))
            r_country = row.get('adm0_a3', 'UNK')
            print(f" -> ID {row['temp_id']}: {sanitize_text(r_name)} ({r_country})")

    # 9. Image Encoding
    print("Encoding visual map...")
    palette = np.zeros((total_regions + 2, 3), dtype=np.uint8)
    for t_id, (r, g, b) in id_to_color_map.items():
        palette[t_id] = [b, g, r] # BGR

    bgr_image = palette[raster_ids]
    
    print(f"Saving PNG: {CONFIG['output_png']}...")
    cv2.imwrite(CONFIG["output_png"], bgr_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    
    print("--- Done! ---")

if __name__ == "__main__":
    main()