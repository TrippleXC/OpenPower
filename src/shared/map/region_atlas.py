import os
import time
import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict, Union
from functools import lru_cache

class RegionAtlas:
    """
    High-Performance Region Manager.
    
    Responsibilities:
    1. Loads a color-coded 'province map' image.
    2. Optimizes it into a packed 32-bit integer array (for fast ID lookups).
    3. Pre-calculates the bounding box for every region to speed up rendering.
    4. Provides fast methods to query region IDs and render overlay textures.
    
    Performance Strategy:
    - Uses Binary Caching (.npy) for both map data and metadata.
    - Uses caching (@lru_cache) for overlay generation.
    - Uses Region of Interest (ROI) slicing to avoid processing the whole map.
    """

    def __init__(self, image_path: str, cache_dir: str = ".cache"):
        """
        Args:
            image_path (str): Path to the source 'provinces.png'.
            cache_dir (str): Folder where optimized binary files will be stored.
        """
        self.image_path = image_path
        self.cache_dir = cache_dir
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Generate paths for the binary cache files
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        self.map_file = os.path.join(cache_dir, f"{base_name}_packed.npy")
        self.meta_file = os.path.join(cache_dir, f"{base_name}_meta.npy")

        # Runtime storage for bounding boxes: { region_id: (y_min, y_max, x_min, x_max) }
        self.region_bounds: Dict[int, Tuple[int, int, int, int]] = {}

        # Load data (Map + Bounds)
        self.packed_map = self._load_data()
        
        # Store dimensions for bounds checking
        self.height, self.width = self.packed_map.shape

    # =========================================================================
    # INTERNAL: Binary Loading & Baking
    # =========================================================================

    def _load_data(self) -> np.ndarray:
        """
        Loads the map and bounds from binary cache. 
        Rebuilds ('bakes') the cache if the source image has changed.
        """
        if not os.path.exists(self.image_path):
            raise FileNotFoundError(f"Source image not found: {self.image_path}")

        current_mtime = os.path.getmtime(self.image_path)

        # 1. Attempt to load from cache
        if self._is_cache_valid(current_mtime):
            try:
                # Load metadata. allow_pickle=True is needed because we stored a Dict.
                # .item() extracts the dictionary from the 0-d array wrapper.
                meta_data = np.load(self.meta_file, allow_pickle=True).item()
                self.region_bounds = meta_data['bounds']
                
                # Load the packed map array
                return np.load(self.map_file)
            except Exception as e:
                print(f"[RegionAtlas] Cache load failed ({e}). Rebuilding...")

        # 2. Cache is stale or missing -> Rebuild
        print("[RegionAtlas] Source map changed. Baking optimized data...")
        return self._rebuild_cache(current_mtime)

    def _is_cache_valid(self, current_mtime: float) -> bool:
        """Returns True if cache files exist and timestamp matches source."""
        if not os.path.exists(self.map_file) or not os.path.exists(self.meta_file):
            return False
        try:
            # We only load the small metadata file to check the timestamp
            meta = np.load(self.meta_file, allow_pickle=True).item()
            return meta.get('mtime') == current_mtime
        except Exception:
            return False

    def _rebuild_cache(self, current_mtime: float) -> np.ndarray:
        """
        The 'Baking' process:
        1. Read Image.
        2. Pack RGB -> Int32.
        3. Scan map to find Bounding Box for every Region ID.
        4. Save everything to .npy.
        """
        t0 = time.time()
        
        # Load image via OpenCV
        img = cv2.imread(self.image_path)
        if img is None:
            raise ValueError(f"Failed to decode image at {self.image_path}")

        # --- Step 1: Pack Colors ---
        # Formula: ID = B | (G << 8) | (R << 16)
        b, g, r = cv2.split(img)
        packed = b.astype(np.int32) | (g.astype(np.int32) << 8) | (r.astype(np.int32) << 16)

        # --- Step 2: Calculate Bounds ---
        print("[RegionAtlas] Pre-calculating region bounds... (This happens once)")
        bounds_cache = {}
        unique_ids = np.unique(packed)
        
        for rid in unique_ids:
            if rid == 0: continue # Skip Ocean/Background
            
            # Find all pixels belonging to this ID
            ys, xs = np.where(packed == rid)
            
            # Store tuple: (y_min, y_max, x_min, x_max)
            if len(xs) > 0:
                bounds_cache[rid] = (np.min(ys), np.max(ys), np.min(xs), np.max(xs))

        self.region_bounds = bounds_cache

        # --- Step 3: Save to Disk ---
        # Save the heavy map array
        np.save(self.map_file, packed)

        # Save metadata (Timestamp + Bounds Dict)
        meta_payload = {'mtime': current_mtime, 'bounds': bounds_cache}
        np.save(self.meta_file, meta_payload)

        print(f"[RegionAtlas] Optimization complete in {time.time() - t0:.2f}s")
        return packed

    # =========================================================================
    # PUBLIC: Core Utilities
    # =========================================================================

    def get_region_at(self, x: int, y: int) -> int:
        """
        Fast O(1) lookup of the region ID at pixel coordinates (x, y).
        Returns 0 if out of bounds.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return int(self.packed_map[y, x])
        return 0

    def pack_color(self, r: int, g: int, b: int) -> int:
        """Helper: RGB -> Packed Int ID"""
        return int(b) | (int(g) << 8) | (int(r) << 16)

    def unpack_color(self, packed_id: int) -> Tuple[int, int, int]:
        """Helper: Packed Int ID -> (R, G, B)"""
        b = packed_id & 255
        g = (packed_id >> 8) & 255
        r = (packed_id >> 16) & 255
        return (r, g, b)

    # =========================================================================
    # PUBLIC: Rendering (Optimized)
    # =========================================================================

    def generate_political_view(self, 
                              region_owner_map: Dict[int, str], 
                              owner_colors: Dict[str, Tuple[int, int, int]]) -> np.ndarray:
        """
        Generates the full political map texture using vectorized Look-Up Tables (LUT).
        Very fast even for 4k maps.
        """
        t0 = time.time()
        max_id = np.max(self.packed_map)
        
        # Prepare Look-Up Tables
        # Indices = Region IDs, Values = Color Channels
        lut_r = np.zeros(max_id + 1, dtype=np.uint8)
        lut_g = np.zeros(max_id + 1, dtype=np.uint8)
        lut_b = np.zeros(max_id + 1, dtype=np.uint8)
        
        # Populate LUTs
        for region_id, owner_tag in region_owner_map.items():
            if region_id > max_id: continue
            
            c = owner_colors.get(owner_tag, (128, 128, 128))
            lut_r[region_id] = c[0]
            lut_g[region_id] = c[1]
            lut_b[region_id] = c[2]

        # Apply LUTs (Vectorized mapping)
        r = lut_r[self.packed_map]
        g = lut_g[self.packed_map]
        b = lut_b[self.packed_map]
        
        # Create Alpha channel: 180 where colored, 0 where empty
        a = np.where((r > 0) | (g > 0) | (b > 0), 180, 0).astype(np.uint8)

        # Merge to RGBA
        res = cv2.merge([r, g, b, a])
        print(f"[RegionAtlas] Political view generated in {time.time() - t0:.3f}s")
        return res

    @lru_cache(maxsize=128)
    def render_country_overlay(self, 
                             region_ids: Tuple[int, ...], 
                             border_color: Tuple[int, int, int] = (255, 255, 255),
                             thickness: int = 3) -> Tuple[Optional[np.ndarray], int, int]:
        """
        Generates a cropped overlay image highlighting the borders of the specified regions.
        
        Optimizations:
        1. Uses @lru_cache to instantly return results for repeated hovers.
        2. Uses pre-calculated bounds to avoid scanning the map.
        3. Slices only the relevant sub-region (ROI) for processing.

        Args:
            region_ids: TUPLE of IDs (Must be tuple to be hashable for caching).
            border_color: RGB tuple for the outline.
            thickness: Line thickness.

        Returns:
            (overlay_image_rgba, x_offset, y_offset)
        """
        if not region_ids:
            return None, 0, 0

        # --- Step 1: Quick Bounds Lookup (O(1)) ---
        # Gather the bounds of all regions in the list
        sys, lys, sxs, lxs = [], [], [], []
        found_any = False
        
        for rid in region_ids:
            if rid in self.region_bounds:
                y1, y2, x1, x2 = self.region_bounds[rid]
                sys.append(y1); lys.append(y2)
                sxs.append(x1); lxs.append(x2)
                found_any = True
        
        if not found_any:
            return None, 0, 0

        # --- Step 2: Determine Global ROI ---
        pad = thickness + 2
        
        # Find the "Super Bounding Box" covering all regions + padding
        roi_y_min = max(0, min(sys) - pad)
        roi_y_max = min(self.height, max(lys) + pad)
        roi_x_min = max(0, min(sxs) - pad)
        roi_x_max = min(self.width, max(lxs) + pad)

        # --- Step 3: Fast Slicing ---
        # Extract ONLY the small chunk of the map we need to process
        roi_map = self.packed_map[roi_y_min:roi_y_max, roi_x_min:roi_x_max]

        # --- Step 4: Masking & Contours on ROI ---
        # Create boolean mask
        if len(region_ids) == 1:
            mask = (roi_map == region_ids[0])
        else:
            mask = np.isin(roi_map, region_ids)
            
        mask_uint8 = mask.astype(np.uint8) * 255

        # Find borders using OpenCV
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None, 0, 0

        # Create transparent buffer
        h, w = roi_map.shape
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        
        # Draw contours
        # border_color + (255,) appends Alpha channel (255 = Opaque)
        cv2.drawContours(overlay, contours, -1, border_color + (255,), thickness)

        return overlay, roi_x_min, roi_y_min