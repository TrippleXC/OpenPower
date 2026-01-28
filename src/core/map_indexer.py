import hashlib
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Optional

class MapIndexer:
    """
    Handles the caching and retrieval of heavy map indexing operations.
    Follows the 'Composition over Inheritance' principle by isolating
    logic from the main renderer.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_indices(self, 
                    source_path: Path, 
                    map_data_array: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retrieves map indices from cache if valid, otherwise computes them.
        
        Args:
            source_path: Path to the original map image (used for integrity check).
            map_data_array: The raw numpy array of the map data to process if cache misses.
            
        Returns:
            Tuple containing (unique_ids, dense_map_indices)
        """
        # 1. Generate a unique filename for the cache based on the map name
        # We append .npz for numpy compressed archive
        cache_path = self.cache_dir / f"{source_path.stem}_index.npz"
        
        # 2. Calculate the current hash of the source file
        current_hash = self._compute_file_hash(source_path)

        # 3. Try to load from cache
        cached_data = self._load_from_cache(cache_path, current_hash)
        
        if cached_data:
            print(f"[MapIndexer] Cache hit for {source_path.name}. Loaded instantly.")
            return cached_data

        # 4. Cache miss: Compute, Save, Return
        print(f"[MapIndexer] Cache miss for {source_path.name}. Computing indices (this may take a moment)...")
        return self._compute_and_cache(map_data_array, cache_path, current_hash)

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Computes SHA-256 hash of the file content for data integrity.
        Reads in chunks to define memory usage.
        """
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read 4MB chunks
                for chunk in iter(lambda: f.read(4096 * 1024), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except FileNotFoundError:
            # Fallback if file is missing (though unlikely in this flow)
            return "FILE_NOT_FOUND"

    def _load_from_cache(self, cache_path: Path, current_hash: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Attempts to load data. Returns None if cache is missing or hash mismatch.
        """
        if not cache_path.exists():
            return None

        try:
            # Load the archive
            # link: https://numpy.org/doc/stable/reference/generated/numpy.load.html
            with np.load(cache_path) as data:
                stored_hash = str(data['hash'])
                
                # INTEGRITY CHECK
                if stored_hash != current_hash:
                    print("[MapIndexer] Cache outdated (hash mismatch).")
                    return None
                
                # Return copies of the arrays to ensure they are writable/safe
                return data['unique_ids'], data['dense_map']
        except Exception as e:
            print(f"[MapIndexer] Failed to load cache: {e}")
            return None

    def _compute_and_cache(self, 
                           map_array: np.ndarray, 
                           cache_path: Path, 
                           current_hash: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Performs the heavy np.unique operation and saves the result.
        """
        # The heavy operation
        unique_ids, dense_map = np.unique(map_array, return_inverse=True)
        
        # Save compressed. 
        # We store the hash inside the file to verify integrity later.
        # link: https://numpy.org/doc/stable/reference/generated/numpy.savez_compressed.html
        np.savez_compressed(
            cache_path, 
            unique_ids=unique_ids, 
            dense_map=dense_map, 
            hash=current_hash
        )
        
        return unique_ids, dense_map