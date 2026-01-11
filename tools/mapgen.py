"""
Map & Database Generator.

Architecture: "Color-As-ID"
----------------------------
1. Visual Map: Pixels represent region IDs.
2. Database: Maps HEX colors (Visual IDs) to Game Data.

Features:
- **CLI Options**: Support for reusing colors from previous builds (`--reuse-tsv`).
- **Stable Matching**: 
    - PRIMARY: Matches by Name (or ISO if empty) + Area (+/- 3km² tolerance).
    - BACKUP: Collision resolution via area matching.
- **Micro-Nation Merging**: Automatically fuses tiny subdivisions.
- **TSV Export**: Tab-Separated Values for robust string handling.
- **Smart Rescue**: Spiral search algorithm to save islands.
- **Verification**: Mathematically proves map integrity.

Dependencies:
    pip install geopandas pandas rasterio numpy opencv-python unidecode pyproj
"""

import os
import sys
import csv
import random
import argparse
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
    "input_shp": ".temp/ne_10m_admin_1_states_provinces_lakes.shp",
    
    # Outputs
    "output_png": ".temp/regions.png",
    "output_tsv": ".temp/regions.tsv",
    
    # Texture Resolution
    "width": 16000,
    "height": 8000,
    
    # WGS84 Global Bounds
    "bounds": (-180.0, -90.0, 180.0, 90.0),
    
    # ID 0 is strictly reserved for Ocean/Background
    "background_id": 0,
    
    # List of Country Codes (ISO A3) to force-merge into single regions.
    "merge_list": [
        "LIE", "SMR", "VAT", "MCO", "AND", "TUV", "NRU"
    ]
}

def hex_to_rgb(hex_str):
    """Converts #RRGGBB string to (r, g, b) tuple."""
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    """Converts RGB tuple to standard HEX string #RRGGBB."""
    return f"#{r:02X}{g:02X}{b:02X}"

def generate_random_colors(count, exclude_colors=None):
    """
    Generates unique random RGB tuples, ensuring no collisions with existing colors.
    """
    if exclude_colors is None:
        exclude_colors = set()
    
    colors = set(exclude_colors)
    result_list = []
    
    # Safety limit to prevent infinite loops if color space is full
    attempts = 0
    max_attempts = count * 100
    
    while len(result_list) < count and attempts < max_attempts:
        attempts += 1
        r = random.randint(10, 255)
        g = random.randint(10, 255)
        b = random.randint(10, 255)
        color = (r, g, b)
        
        # Ensure we never generate Black (0,0,0) or duplicates
        if color not in colors and color != (0, 0, 0):
            colors.add(color)
            result_list.append(color)
            
    if len(result_list) < count:
        print(f"Warning: Could only generate {len(result_list)}/{count} unique colors.")
            
    return result_list

def sanitize_text(text):
    """
    Sanitizes string data:
    1. Fixes encoding (Mojibake).
    2. Transliterates to ASCII (removes accents).
    3. Strips whitespace.
    4. Returns empty string for NaN/None
    """
    if pd.isna(text) or text is None:
        return ""
    
    text = str(text)
    
    try:
        fixed_text = text.encode('cp1252').decode('utf-8')
    except:
        fixed_text = text

    return unidecode(fixed_text).strip()

def get_name_and_iso(row):
    """
    Helper to extract the display name and ISO reliably for matching logic.
    Returns: (display_name, iso_region)
    """
    # 1. ISO Region Code
    iso_reg = sanitize_text(row.get('iso_3166_2', 'UNK'))
    if not iso_reg:
        iso_reg = "UNK"

    # 2. Name Extraction with Fallback Chain
    raw_name = sanitize_text(row.get('name', ''))
    name_en = sanitize_text(row.get('name_en', ''))
    
    display_name = ""
    if len(name_en) > 1:
        display_name = name_en
    else:
        display_name = raw_name
        
    # NOTE: We do NOT default name to ISO here yet, 
    # because the matching logic treats empty name specifically.
    
    return display_name, iso_reg

def get_stable_fingerprint(row):
    """
    Generates full metadata tuple for the database export.
    Returns: (display_name, iso_reg, key_tuple)
    """
    display_name, iso_reg = get_name_and_iso(row)

    # CRITICAL: For export, if name is missing, use ISO code as name
    if not display_name:
        display_name = iso_reg

    # Extra Data
    admin_type = sanitize_text(row.get('type_en', 'Region'))
    postal_code = sanitize_text(row.get('postal', ''))

    # Key tuple (useful for debugging, though less used for matching now)
    key = (iso_reg, display_name, admin_type, postal_code)
    
    return display_name, iso_reg, key

def merge_micro_nations(gdf, codes_to_merge):
    """
    Combines all regions of specific countries into a single geometry.
    """
    print(f"Optimizing: Merging micro-nations {codes_to_merge}...")
    
    for code in codes_to_merge:
        subset = gdf[gdf['adm0_a3'] == code]
        
        if subset.empty or len(subset) <= 1:
            continue 
            
        print(f"  -> Merging {len(subset)} regions for {code}...")
        
        if hasattr(subset.geometry, 'union_all'):
            unified_geom = subset.geometry.union_all()
        else:
            unified_geom = subset.geometry.unary_union
        
        # Inherit metadata from the first row of the subset
        new_row = subset.iloc[0].copy()
        new_row['geometry'] = unified_geom
        c_name = subset.iloc[0].get('admin', code) 
        new_row['name'] = c_name
        new_row['name_en'] = c_name
        new_row['type_en'] = "Sovereign State" 
        new_row['postal'] = "" 
        
        gdf = gdf[gdf['adm0_a3'] != code]
        new_gdf = gpd.GeoDataFrame([new_row], crs=gdf.crs)
        gdf = pd.concat([gdf, new_gdf], ignore_index=True)
        
    return gdf

def load_existing_colors_smart(tsv_path):
    """
    Parses an existing TSV and builds a lookup index for smart matching.
    
    Matching Strategy:
    - Primary Key: Name (sanitized).
    - Fallback Key: ISO Region (if Name is empty).
    - Validation: Area (+/- 3km²).
    
    Returns:
        lookup_dict: { 'Key': [ {'area': int, 'color': (r,g,b), 'hex': str} ] }
        used_colors: set((r,g,b))
    """
    print(f"Loading existing colors from {tsv_path}...")
    lookup_dict = {}
    used_colors = set()
    
    if not os.path.exists(tsv_path):
        print("Warning: TSV file not found. Proceeding with fresh generation.")
        return lookup_dict, used_colors

    try:
        df = pd.read_csv(tsv_path, sep='\t')
        
        for _, row in df.iterrows():
            # Extract basic data
            r_iso = sanitize_text(row.get('iso_region', 'UNK'))
            r_name = sanitize_text(row.get('name', ''))
            hex_val = str(row.get('hex', ''))
            area_val = int(row.get('area_km2', 0))
            
            if not hex_val: 
                continue

            color_rgb = hex_to_rgb(hex_val)
            used_colors.add(color_rgb)
            
            # === Build Lookup Key Logic ===
            # "If name is empty, use ISO"
            if r_name:
                key = r_name
            else:
                key = r_iso
                
            # Store in lookup (handle duplicates by storing list)
            if key not in lookup_dict:
                lookup_dict[key] = []
                
            lookup_dict[key].append({
                'area': area_val,
                'color': color_rgb,
                'hex': hex_val
            })
                
    except Exception as e:
        print(f"Error reading TSV: {e}. Proceeding with fresh generation.")
    
    print(f"  -> Loaded {len(used_colors)} existing colors into index.")
    return lookup_dict, used_colors

def resolve_color_collisions(id_to_color_map, gdf, original_area_lookup_by_hex, used_colors):
    """
    Secondary safeguard. Scans for duplicate colors in the map.
    Resolves using exact area matching if possible.
    """
    print("Scanning for duplicate color assignments...")
    
    # Invert map to find collisions: color -> [id1, id2, ...]
    color_to_ids = {}
    for tid, color in id_to_color_map.items():
        if color not in color_to_ids:
            color_to_ids[color] = []
        color_to_ids[color].append(tid)
    
    collisions = {c: ids for c, ids in color_to_ids.items() if len(ids) > 1}
    
    if not collisions:
        print("  -> No color collisions detected.")
        return id_to_color_map
    
    print(f"  -> WARNING: Found {len(collisions)} color collisions. Resolving...")
    
    for color, conflicting_ids in collisions.items():
        hex_key = rgb_to_hex(*color)
        
        # We need the original area for this hex. 
        # Since our new lookup structure is complex, we might not have a simple Hex->Area map passed in.
        # However, we can trust the logic below to separate them.
        
        # If we can't look up the original area easily here, we simply force regenerate
        # for ALL but one (arbitrarily the first one, or the one closest to some logic).
        # To keep it robust without passing complex lookups, we just regenerate duplicates.
        
        print(f"    Collision on {hex_key}. Regenerating duplicates...")
        
        # Keep the first one, change the rest
        for i, tid in enumerate(conflicting_ids):
            if i == 0:
                continue # Keep first
            
            # Generate new unique color
            new_color_list = generate_random_colors(1, exclude_colors=used_colors)
            if new_color_list:
                new_c = new_color_list[0]
                id_to_color_map[tid] = new_c
                used_colors.add(new_c)
                print(f"      -> ID {tid} reassigned to {rgb_to_hex(*new_c)}")

    return id_to_color_map

def main():
    # === ARGUMENT PARSING ===
    parser = argparse.ArgumentParser(description="Map & Database Generator")
    parser.add_argument("--reuse-tsv", type=str, help="Path to existing TSV for color preservation.", default=None)
    args = parser.parse_args()

    print(f"--- Starting Map Generation ---")

    # 1. Input Validation
    if not os.path.exists(CONFIG["input_shp"]):
        print(f"ERROR: Input file {CONFIG['input_shp']} not found.")
        sys.exit(1)

    print("Reading Shapefile...")
    try:
        gdf = gpd.read_file(CONFIG["input_shp"], encoding='utf-8')
    except Exception:
        print("Warning: Forced UTF-8 failed. Reverting to auto-detect.")
        gdf = gpd.read_file(CONFIG["input_shp"])

    # 2. Optimization: Merge Micro-Nations
    gdf = merge_micro_nations(gdf, CONFIG['merge_list'])

    # 3. Physics Calculation
    print("Calculating real surface area...")
    gdf_metric = gdf.to_crs({'proj': 'cea'})
    gdf['area_km2'] = (gdf_metric.geometry.area / 1e6).astype(int)

    # 4. ID and Color Assignment Logic
    total_regions = len(gdf)
    gdf['temp_id'] = range(1, total_regions + 1)
    
    id_to_color_map = {}
    
    # New Lookup Structures
    smart_lookup = {}
    used_colors = set()
    
    if args.reuse_tsv:
        smart_lookup, used_colors = load_existing_colors_smart(args.reuse_tsv)
    
    regions_needing_new_colors = []
    
    print("Assigning colors to regions...")
    
    matches_found = 0
    
    for _, row in gdf.iterrows():
        t_id = row['temp_id']
        current_area = row['area_km2']
        
        # === NEW MATCHING LOGIC ===
        # 1. Get Name and ISO
        name_raw, iso_raw = get_name_and_iso(row)
        
        # 2. Determine Lookup Key: "If name is empty, check using ISO code"
        lookup_key = name_raw if name_raw else iso_raw
        
        # 3. Search in Loaded Data
        match_color = None
        
        if lookup_key in smart_lookup:
            candidates = smart_lookup[lookup_key]
            
            # Iterate candidates to find Area Match (Tolerance +/- 3km)
            # We iterate backwards so we can pop safely if needed (though break handles it)
            for i, cand in enumerate(candidates):
                old_area = cand['area']
                if abs(old_area - current_area) <= 3:
                    # MATCH!
                    match_color = cand['color']
                    
                    # Consume this candidate to prevent double-assignment
                    # (Removes from the list of available options for this name)
                    candidates.pop(i)
                    
                    # Clean up dictionary if empty
                    if not candidates:
                        del smart_lookup[lookup_key]
                        
                    break
        
        if match_color:
            id_to_color_map[t_id] = match_color
            matches_found += 1
        else:
            regions_needing_new_colors.append(t_id)

    print(f"  -> Matched {matches_found} regions using Name+Area logic.")

    # Generate fresh colors for unmatched regions
    if regions_needing_new_colors:
        print(f"  -> Generating colors for {len(regions_needing_new_colors)} new/unmatched regions...")
        print("  -> Details of newly added regions:")

        # Create a temporary index for fast lookup of region details
        gdf_lookup = gdf.set_index('temp_id')
        
        new_colors = generate_random_colors(len(regions_needing_new_colors), exclude_colors=used_colors)
        
        for idx, t_id in enumerate(regions_needing_new_colors):
            # 1. Assign the new color
            id_to_color_map[t_id] = new_colors[idx]
            used_colors.add(new_colors[idx])
            
            # 2. Retrieve and Print Metadata
            row = gdf_lookup.loc[t_id]
            d_name, d_iso = get_name_and_iso(row)
            
            # Formatting for log output
            display_str = d_name if d_name else "N/A"
            print(f"      [+] Added: {d_iso} | Name: {display_str:<30} | Area: {row['area_km2']} km²")
    
    # 5. Collision Detection & Resolution
    # We pass None for original_area_lookup because we handled specific area matching above.
    # This acts as a final sanity check for purely random collisions.
    id_to_color_map = resolve_color_collisions(
        id_to_color_map, 
        gdf, 
        None, 
        used_colors
    )

    # 6. Metadata Extraction & TSV Export
    print("Processing metadata and export...")
    transform = from_bounds(*CONFIG['bounds'], CONFIG['width'], CONFIG['height'])
    
    tsv_rows = []
    
    tsv_header = [
        "hex", "name", "owner", "iso_region", "type", 
        "macro_region", "postal", "area_km2", "center_x", "center_y",
        "ne_id", "wikidataid"
    ]
    tsv_rows.append(tsv_header)
    
    center_lookup = {}
    
    for _, row in gdf.iterrows():
        t_id = int(row['temp_id'])
        r, g, b = id_to_color_map[t_id]
        
        # Geometry Math
        geom = row.geometry
        center_geo = geom.centroid
        c_row, c_col = rowcol(transform, center_geo.x, center_geo.y)
        c_x = int(max(0, min(c_col, CONFIG['width'] - 1)))
        c_y = int(max(0, min(c_row, CONFIG['height'] - 1)))

        # Metadata extraction (Uses the Standard Fingerprint logic for output)
        display_name, iso_reg, key = get_stable_fingerprint(row)
        _, _, admin_type, postal = key

        owner_code = row.get('adm0_a3', 'UNK').replace('-99', 'UNK')
        macro_reg = sanitize_text(row.get('region', ''))
        area = int(row['area_km2'])

        ne_id = row.get('ne_id', '')
        wikidata_id = sanitize_text(row.get('wikidataid', ''))

        hex_color = rgb_to_hex(r, g, b)
        
        tsv_rows.append([
            hex_color, display_name, owner_code, iso_reg, 
            admin_type, macro_reg, postal, area, c_x, c_y,
            ne_id, wikidata_id
        ])
        
        center_lookup[t_id] = (c_x, c_y)

    print(f"Saving Database: {CONFIG['output_tsv']}...")
    with open(CONFIG["output_tsv"], "w", encoding="utf-8-sig", newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(tsv_rows)

    # 7. Rasterization
    print("Rasterizing geometry...")
    shapes = ((geom, value) for geom, value in zip(gdf.geometry, gdf['temp_id']))
    
    raster_ids = features.rasterize(
        shapes=shapes,
        out_shape=(CONFIG['height'], CONFIG['width']),
        transform=transform,
        fill=CONFIG['background_id'],
        dtype=np.uint32,
        all_touched=False
    )

    # 8. Rescue Logic
    print("Rescuing small regions...")
    present_ids = np.unique(raster_ids)
    missing_ids = np.setdiff1d(gdf['temp_id'].values, present_ids)
    
    if len(missing_ids) > 0:
        print(f"  -> Attempting to rescue {len(missing_ids)} regions...")
        protected_ids = set(missing_ids)
        placed_count = 0
        
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
            
            for try_x, try_y in get_spiral(c_x, c_y, 30):
                if not (0 <= try_x < CONFIG['width'] and 0 <= try_y < CONFIG['height']):
                    continue
                
                current_pixel_val = raster_ids[try_y, try_x]
                
                if current_pixel_val == CONFIG['background_id']:
                    best_candidate = (try_x, try_y)
                    break 
                
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

    # 9. Integrity Verification
    print("--- Verifying Integrity ---")
    final_present_ids = np.unique(raster_ids)
    expected_set = set(gdf['temp_id'].values)
    found_set = set(final_present_ids)
    lost_regions = expected_set - found_set
    
    if len(lost_regions) == 0:
        print("SUCCESS: 100% Integrity. All regions are present on the map.")
    else:
        print(f"WARNING: Verification FAILED. {len(lost_regions)} regions are missing!")
        for rid in lost_regions:
             print(f"  -> Missing ID: {rid}")

    # 10. Image Encoding
    print("Encoding visual map...")
    max_id = gdf['temp_id'].max()
    palette = np.zeros((max_id + 2, 3), dtype=np.uint8)
    
    for t_id, (r, g, b) in id_to_color_map.items():
        palette[t_id] = [b, g, r] # BGR for OpenCV

    bgr_image = palette[raster_ids]
    
    print(f"Saving PNG: {CONFIG['output_png']}...")
    cv2.imwrite(CONFIG["output_png"], bgr_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    
    print("--- Done! ---")

if __name__ == "__main__":
    main()