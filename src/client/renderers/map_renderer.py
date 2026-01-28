import arcade
import arcade.gl
import numpy as np
from array import array
from typing import Optional, List, Dict, Tuple, Union, Set
from pathlib import Path
from pyglet import gl

# Internal imports
from src.core.map_data import RegionMapData
from src.core.map_indexer import MapIndexer
from src.client.shader_registry import ShaderRegistry

class MapRenderer:
    """
    Handles the high-performance rendering of the game map, including terrain
    sprites and the compute-heavy political overlay.
    
    Architecture:
        - Uses caching logic (MapIndexer).
        - Utilizes a custom OpenGL shader pipeline to render thousands of regions 
          efficiently by using a Lookup Table (LUT) texture rather than individual geometry.
    """

    def __init__(self, 
                 map_data: RegionMapData, 
                 map_img_path: Path, 
                 terrain_img_path: Path):
        
        # We need the window context to create textures and buffers.
        self.window = arcade.get_window()
        self.ctx = self.window.ctx
        self.map_data = map_data
        self.width = map_data.width
        self.height = map_data.height
        
        # --- MAPPINGS ---
        # We maintain bidirectional mappings between 'Real' IDs (from map_data)
        # and 'Dense' IDs (0..N sequential indices used for the LUT texture).
        # This reduces the texture memory requirement from MaxID size to UniqueCount size.
        self.real_to_dense: Dict[int, int] = {}
        self.dense_to_real: Union[List[int], np.ndarray] = []

        # --- CACHING COMPONENT ---
        # Logic for hashing and caching heavy numpy operations is isolated 
        # in MapIndexer to keep this renderer focused on visualization (CoI).
        # Cache files are stored in a 'cache' subdirectory next to the map image.
        self.indexer = MapIndexer(map_img_path.parent / ".cache")

        # --- SELECTION STATE ---
        self.single_select_dense_id: int = -1
        self.multi_select_dense_ids: Set[int] = set()
        
        # We track the previous selection set to optimize texture updates.
        # Instead of rewriting the whole LUT, we only update changed pixels.
        self.prev_multi_select_dense_ids: Set[int] = set()

        # --- TEXTURE CONFIGURATION ---
        # 4096^2 covers ~16 million unique regions, sufficient for any grand strategy map.
        self.lut_dim = 4096
        # Initialize with 0 (Transparent/No Country).
        # Shape is (N, 4) for RGBA.
        self.lut_data = np.full((self.lut_dim * self.lut_dim, 4), 0, dtype=np.uint8)

        # Cache for country data to allow rapid rebuilding of the LUT 
        # without querying the core game state every frame.
        self._cached_ownership: Dict[int, str] = {}
        self._cached_colors: Dict[str, Tuple[int, int, int]] = {}

        self.terrain_sprite: Optional[arcade.Sprite] = None
        self.terrain_list: Optional[arcade.SpriteList] = None
        
        # --- INITIALIZATION SEQUENCE ---
        # Resources must be loaded before GLSL, as the shader requires 
        # texture dimensions and handles established here.
        self._init_resources(terrain_img_path, map_img_path) 
        self._init_glsl()

    def get_center(self) -> Tuple[float, float]:
        """Returns the world center coordinates of the map for camera positioning."""
        return self.width / 2.0, self.height / 2.0
    
    def _init_resources(self, terrain_path: Path, map_path: Path):
        """
        Loads textures and computes the region index map.
        Uses the MapIndexer to avoid re-computing unique IDs on every startup.
        """
        # 1. Setup Terrain Layer
        self.terrain_list = arcade.SpriteList()

        if terrain_path.exists():
            self.terrain_sprite = arcade.Sprite(terrain_path)
            # Ensure the sprite matches the logical map dimensions exactly
            self.terrain_sprite.width = self.width
            self.terrain_sprite.height = self.height
            self.terrain_sprite.center_x = self.width / 2
            self.terrain_sprite.center_y = self.height / 2
            self.terrain_list.append(self.terrain_sprite)
        else:
            # We log critical errors but allow execution to continue (perhaps with a black background)
            # to prevent a hard crash during development.
            print(f"CRITICAL ERROR: Terrain path not found: {terrain_path}")
            self.terrain_sprite = None

        # 2. Re-Index Map (The Optimization)
        print(f"[MapRenderer] Loading region indices...")
        
        # This call handles the hashing, cache checking, and file I/O transparently.
        unique_ids, dense_map = self.indexer.get_indices(
            source_path=map_path,
            map_data_array=self.map_data.packed_map
        )
        
        self.dense_to_real = unique_ids
        # Rebuilding the dictionary is fast (O(N) on regions) and safer to do in-memory 
        # than serializing/deserializing dict objects.
        self.real_to_dense = {real_id: i for i, real_id in enumerate(unique_ids)}
        
        print(f"[MapRenderer] Indexed {len(unique_ids)} unique regions.")

        # 3. Create Map Data Texture
        # We must convert the dense integer map (0..N) into an RGB texture representation.
        # This texture is never seen by the user; it is read by the shader to look up IDs.
        dense_map = dense_map.reshape((self.height, self.width)).astype(np.uint32)
        r = ((dense_map >> 16) & 0xFF).astype(np.uint8)
        g = ((dense_map >> 8) & 0xFF).astype(np.uint8)
        b = (dense_map & 0xFF).astype(np.uint8)
        
        encoded_data = np.dstack((r, g, b))
        
        # OpenGL coordinate system (bottom-left) vs Image (top-left) requires flipping.
        encoded_data = np.flipud(encoded_data)

        # Essential: Default pack alignment is 4 bytes. If row width is not a multiple of 4,
        # the texture will shear or segfault. We set alignment to 1 for safety.
        # Reference: https://www.khronos.org/opengl/wiki/Pixel_Transfer#Pixel_layout
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

        self.map_texture = self.ctx.texture(
            (self.width, self.height),
            components=3,
            data=encoded_data.tobytes(),
            # NEAREST filter is mandatory. Interpolation (LINEAR) would blend ID 5 and ID 6 
            # into a non-existent ID (e.g., 5.5), breaking the lookup logic.
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )
        
        # 4. Create Lookup Texture (LUT)
        # This texture holds the color state for every region.
        # X/Y coords in this texture correspond to the Dense ID of the region.
        self.lookup_texture = self.ctx.texture(
            (self.lut_dim, self.lut_dim),
            components=4,
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )
        # Write initial blank state immediately to prevent visual garbage.
        self.lookup_texture.write(self.lut_data.tobytes())

    def _init_glsl(self):
        """
        Compiles the shader program and sets up the full-screen quad geometry.
        """
        # Standard full-screen quad coordinates
        # Format: x, y, u, v
        buffer_data = array('f', [
            0.0, 0.0, 0.0, 0.0,
             self.width, 0.0, 1.0, 0.0,
            0.0,  self.height, 0.0, 1.0,
             self.width,  self.height, 1.0, 1.0,
        ])
        
        self.quad_buffer = self.ctx.buffer(data=buffer_data)
        self.quad_geometry = self.ctx.geometry(
            [arcade.gl.BufferDescription(self.quad_buffer, '2f 2f', ['in_vert', 'in_uv'])],
            mode=self.ctx.TRIANGLE_STRIP
        )

        shader_source = ShaderRegistry.load_bundle(ShaderRegistry.POLITICAL_V, ShaderRegistry.POLITICAL_F)
        self.program = self.ctx.program(
            vertex_shader=shader_source["vertex_shader"],
            fragment_shader=shader_source["fragment_shader"]
        )
        
        # Configure static uniforms
        # Texture unit 0: The map ID texture
        # Texture unit 1: The color Lookup Table
        self.program['u_map_texture'] = 0
        self.program['u_lookup_texture'] = 1
        self.program['u_texture_size'] = (float(self.width), float(self.height))
        self.program['u_lut_dim'] = float(self.lut_dim)
        self.program['u_selected_id'] = -1

    def update_political_layer(self, region_ownership: Dict[int, str], country_colors: Dict[str, Tuple[int, int, int]]):
        """
        Full update of the political map visualization.
        Called when map state changes (e.g., province occupation, annexation).
        """
        self._cached_ownership = region_ownership
        self._cached_colors = country_colors
        
        self._rebuild_lut_array()
        
        # Push the entire array to GPU.
        # While updating sub-regions is possible, Python overhead usually makes 
        # a single bulk write faster for updates of this size.
        self.lookup_texture.write(self.lut_data.tobytes())

    def _rebuild_lut_array(self):
        """
        Regenerates the numpy array for the Lookup Table based on current ownership.
        """
        # Reset to 0 (Transparent)
        self.lut_data.fill(0) 

        for real_id, tag in self._cached_ownership.items():
            if real_id in self.real_to_dense:
                dense_id = self.real_to_dense[real_id]
                
                # Safety check for size allocation
                if dense_id < len(self.lut_data):
                    # ID 0 is usually background/ocean; we keep it transparent unless
                    # game logic dictates otherwise.
                    if dense_id == 0: continue 

                    color = self._cached_colors.get(tag, (100, 100, 100))
                    
                    # Highlight logic: If selected, full opacity (255), otherwise partial (200).
                    # This allows terrain to show through slightly for unselected regions.
                    alpha = 255 if dense_id in self.multi_select_dense_ids else 200
                    self.lut_data[dense_id] = [color[0], color[1], color[2], alpha]

    def _update_selection_texture(self):
        """
        Optimized partial update for the LUT when only selection changes.
        Avoids iterating through the entire ownership map.
        """
        # 1. Revert old selection to standard opacity
        for idx in self.prev_multi_select_dense_ids:
            if idx < len(self.lut_data) and idx != 0: 
                # Check if this region actually has an owner/color before modifying
                # We check alpha > 0 to ensure we don't make empty ocean visible
                if self.lut_data[idx, 3] > 0:
                    self.lut_data[idx, 3] = 200

        # 2. Set new selection to full opacity
        for idx in self.multi_select_dense_ids:
            if idx < len(self.lut_data) and idx != 0: 
                if self.lut_data[idx, 3] > 0:
                    self.lut_data[idx, 3] = 255

        # Update tracking set
        self.prev_multi_select_dense_ids = self.multi_select_dense_ids.copy()
        
        # Push update to GPU
        self.lookup_texture.write(self.lut_data.tobytes())

    def set_highlight(self, real_region_ids: List[int]):
        """
        Updates the visual highlight state for specific regions.
        Handles both single-select (shader uniform) and multi-select (LUT alpha manipulation).
        """
        if not real_region_ids:
            self.clear_highlight()
            return

        # Filter valid IDs to prevent key errors
        valid_dense_ids = []
        for rid in real_region_ids:
            if rid in self.real_to_dense:
                valid_dense_ids.append(self.real_to_dense[rid])

        if not valid_dense_ids:
            return

        # Case 1: Single Selection
        # We use a shader uniform for this because it's instant and requires no texture upload.
        if len(valid_dense_ids) == 1:
            self.single_select_dense_id = valid_dense_ids[0]
            
            # Clear multi-select if it was active
            if self.multi_select_dense_ids:
                self.multi_select_dense_ids = set()
                self._update_selection_texture()
        
        # Case 2: Multi-selection
        # We fallback to LUT modification because checking N uniforms in a shader is expensive/limited.
        else:
            self.single_select_dense_id = -1
            new_set = set(valid_dense_ids)
            
            # Only trigger texture update if the set actually changed
            if new_set != self.multi_select_dense_ids:
                self.multi_select_dense_ids = new_set
                self._update_selection_texture()

    def clear_highlight(self):
        """Resets all highlighting."""
        self.single_select_dense_id = -1
        if self.multi_select_dense_ids:
            self.multi_select_dense_ids = set()
            self._update_selection_texture()

    def draw(self, mode: str = "terrain"):
        """
        Main render loop.
        
        Args:
            mode: 'terrain' (default) or 'political'. 
        """
        # 1. Draw Terrain Base
        # We always draw the terrain first. Even in political mode, the terrain 
        # often provides necessary context (coastlines, mountains) underneath the overlay.
        if self.terrain_list:
            self.terrain_list.draw()

        # OPTIMIZATION: Early exit
        # If we are in terrain mode and nothing is highlighted, the overlay is invisible.
        # Skipping the draw call saves fill-rate performance.
        if mode == "terrain" and self.single_select_dense_id == -1 and not self.multi_select_dense_ids:
            return

        # 2. GL State Setup
        # Enable blending so the overlay can be semi-transparent over the terrain.
        self.ctx.enable(self.ctx.BLEND)
        self.ctx.blend_func = self.ctx.BLEND_DEFAULT
        
        # Bind textures to the slots defined in _init_glsl
        self.map_texture.use(0)
        self.lookup_texture.use(1)
        
        # Update view matrices (camera movement)
        self.program['u_view'] = self.window.ctx.view_matrix
        self.program['u_projection'] = self.window.ctx.projection_matrix
        self.program['u_selected_id'] = int(self.single_select_dense_id)
        
        # 3. Mode Logic
        if mode == "political":
            self.program['u_overlay_mode'] = 1
            self.program['u_opacity'] = 0.9
        else:
            # In terrain mode, we only want the selection border/fill to show,
            # so we switch overlay mode to 0 (or whatever the shader logic dictates for "selection only").
            self.program['u_overlay_mode'] = 0
            self.program['u_opacity'] = 1.0 

        # 4. Draw Quad
        self.quad_geometry.render(self.program)

    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> int:
        """
        Converts world coordinates (mouse click) to a region ID.
        """
        # Arcade/GL coords (0 at bottom) vs Image coords (0 at top) usually requires inversion.
        # Assuming map_data accesses are top-down.
        img_y = int(self.height - world_y)
        
        # Bounds check
        if not (0 <= world_x < self.width and 0 <= img_y < self.height):
            return 0
            
        return self.map_data.get_region_id(int(world_x), img_y)