import time
from dataclasses import dataclass
from pathlib import Path
from src.server.session import GameSession
from src.shared.config import GameConfig
from src.shared.map.region_atlas import RegionAtlas
from src.client.services.network_client_service import NetworkClient

@dataclass
class EditorContext:
    """
    Container for assets loaded in the background thread.
    Passed to EditorView so it doesn't have to load them again.
    """
    map_path: Path
    terrain_path: Path      # Path to the artistic background (terrain)
    atlas: RegionAtlas      # Pre-calculated OpenCV/NumPy data
    net_client: NetworkClient

class EditorLoadingTask:
    """
    Handles the heavy lifting of preparing the Editor.
    
    Why this is needed:
        The RegionAtlas uses OpenCV and NumPy to process the map image.
        On large maps (4k+), this can take 1-5 seconds. Doing this on the
        main thread would freeze the UI. We also resolve file paths here.
    """

    def __init__(self, session: GameSession, config: GameConfig):
        self.session = session
        self.config = config
        
        # LoadingTask Protocol
        self.progress: float = 0.0
        self.status_text: str = "Preparing Editor..."

    def run(self) -> EditorContext:
        """
        Executed in background thread by LoadingView.
        """
        # 1. Locate Map Assets
        self.status_text = "Locating map assets..."
        self.progress = 0.1
        
        map_path = self._resolve_map_path()
        terrain_path = self._resolve_terrain_path()
        
        # Brief sleep ensures the UI thread has a chance to render the text update
        # before the heavy CPU blocking operation starts.
        time.sleep(0.1) 

        # 2. Load Region Data (Heavy CPU Work)
        self.status_text = "Processing Region Atlas (CV2)..."
        self.progress = 0.3
        
        # We perform the heavy CV2/NumPy analysis here using the technical map (regions).
        # This is safe to do in a thread because it doesn't touch OpenGL.
        atlas = RegionAtlas(str(map_path), str(self.config.cache_dir))
        
        # 3. Initialize Network
        self.status_text = "Connecting to Session..."
        self.progress = 0.8
        
        net_client = NetworkClient(self.session)
        
        # 4. Finalize
        self.status_text = "Finalizing..."
        self.progress = 1.0
        
        return EditorContext(
            map_path=map_path,
            terrain_path=terrain_path,
            atlas=atlas,
            net_client=net_client
        )

    def _resolve_map_path(self) -> Path:
        """
        Finds the technical region map (defined by specific RGB colors).
        """
        # Try Data Dirs first (User modded content)
        for data_dir in self.config.get_data_dirs():
            candidate = data_dir / "regions" / "regions.png"
            if candidate.exists():
                return candidate
        
        # Fallback to internal assets (Core game content)
        candidate = self.config.get_asset_path("map/regions.png")
        if candidate and candidate.exists():
            return candidate
            
        # Fallback to root (Critical error usually, but we return a path to fail gracefully later)
        return self.config.project_root / "missing_map_placeholder.png"

    def _resolve_terrain_path(self) -> Path:
        """
        Finds the artistic terrain background.
        Convention: It lives in the same folder as regions.png usually.
        """

        candidate = self.config.get_asset_path("maps/terrain.png")
        if candidate and candidate.exists():
            return candidate

        # Return a non-existent path if not found; the renderer handles this gracefully.
        return self.config.project_root / "missing_terrain_placeholder.png"