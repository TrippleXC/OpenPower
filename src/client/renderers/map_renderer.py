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
    Handles the high-performance rendering of the game map.
    
    Refactored for Generic Map Modes:
    This class no longer knows about 'politics' or 'GDP'. It simply accepts 
    a dictionary of {RegionID: RGB} and visualizes it via the Lookup Table (LUT).
    """

    def __init__(self, 
                 map_data: RegionMapData, 
                 map_img_path: Path, 
                 terrain_img_path: Path):
        
        self.window = arcade.get_window()
        self.ctx = self.window.ctx
        self.map_data = map_data
        self.width = map_data.width
        self.height = map_data.height
        
        # --- MAPPINGS ---
        self.real_to_dense: Dict[int, int] = {}
        self.dense_to_real: Union[List[int], np.ndarray] = []

        # --- CACHING COMPONENT ---
        self.indexer = MapIndexer(map_img_path.parent / ".cache")

        # --- SELECTION STATE ---
        self.single_select_dense_id: int = -1
        self.multi_select_dense_ids: Set[int] = set()
        self.prev_multi_select_dense_ids: Set[int] = set()

        # --- VISUALIZATION STATE ---
        # Cache the current color map so we can update selection highlights 
        # without needing the full GameState or re-calculating everything.
        # Format: {RealID: (R, G, B)}
        self._active_color_map: Dict[int, Tuple[int, int, int]] = {}
        
        # Default fallback color (Dark Grey for unmapped regions)
        self._default_color = (40, 40, 40)

        # --- TEXTURE CONFIGURATION ---
        self.lut_dim = 4096
        self.lut_data = np.full((self.lut_dim * self.lut_dim, 4), 0, dtype=np.uint8)

        self.terrain_sprite: Optional[arcade.Sprite] = None
        self.terrain_list: Optional[arcade.SpriteList] = None
        
        self._init_resources(terrain_img_path, map_img_path) 
        self._init_glsl()

    def get_center(self) -> Tuple[float, float]:
        return self.width / 2.0, self.height / 2.0
    
    def _init_resources(self, terrain_path: Path, map_path: Path):
        # 1. Setup Terrain Layer
        self.terrain_list = arcade.SpriteList()

        if terrain_path.exists():
            self.terrain_sprite = arcade.Sprite(terrain_path)
            self.terrain_sprite.width = self.width
            self.terrain_sprite.height = self.height
            self.terrain_sprite.center_x = self.width / 2
            self.terrain_sprite.center_y = self.height / 2
            self.terrain_list.append(self.terrain_sprite)
        else:
            print(f"CRITICAL ERROR: Terrain path not found: {terrain_path}")
            self.terrain_sprite = None

        # 2. Re-Index Map
        print(f"[MapRenderer] Loading region indices...")
        unique_ids, dense_map = self.indexer.get_indices(
            source_path=map_path,
            map_data_array=self.map_data.packed_map
        )
        
        self.dense_to_real = unique_ids
        self.real_to_dense = {real_id: i for i, real_id in enumerate(unique_ids)}
        
        print(f"[MapRenderer] Indexed {len(unique_ids)} unique regions.")

        # 3. Create Map Data Texture (Dense ID Map)
        dense_map = dense_map.reshape((self.height, self.width)).astype(np.uint32)
        r = ((dense_map >> 16) & 0xFF).astype(np.uint8)
        g = ((dense_map >> 8) & 0xFF).astype(np.uint8)
        b = (dense_map & 0xFF).astype(np.uint8)
        
        encoded_data = np.dstack((r, g, b))
        encoded_data = np.flipud(encoded_data)

        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

        self.map_texture = self.ctx.texture(
            (self.width, self.height),
            components=3,
            data=encoded_data.tobytes(),
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )
        
        # 4. Create Lookup Texture (LUT)
        self.lookup_texture = self.ctx.texture(
            (self.lut_dim, self.lut_dim),
            components=4,
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )
        self.lookup_texture.write(self.lut_data.tobytes())

    def _init_glsl(self):
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
        
        self.program['u_map_texture'] = 0
        self.program['u_lookup_texture'] = 1
        self.program['u_texture_size'] = (float(self.width), float(self.height))
        self.program['u_lut_dim'] = float(self.lut_dim)
        self.program['u_selected_id'] = -1

    def update_overlay(self, color_map: Dict[int, Tuple[int, int, int]]):
        """
        Updates the map overlay with new colors.
        
        Args:
            color_map: Dictionary mapping Real Region IDs to (R, G, B) tuples.
                       Regions not in the map will use the default dark grey.
        """
        self._active_color_map = color_map
        self._rebuild_lut_array()
        self.lookup_texture.write(self.lut_data.tobytes())

    def _rebuild_lut_array(self):
        """
        Regenerates the numpy array for the Lookup Table based on _active_color_map.
        """
        # Reset to 0 (Transparent)
        self.lut_data.fill(0) 

        # We iterate over the *Real* IDs provided in the color map
        for real_id, color in self._active_color_map.items():
            # Translate Real ID -> Dense ID for texture coordinates
            if real_id in self.real_to_dense:
                dense_id = self.real_to_dense[real_id]
                
                if dense_id < len(self.lut_data):
                    # ID 0 is usually background/ocean; ignore unless specified
                    if dense_id == 0: continue 

                    # Alpha Logic: 
                    # Highlighting is done via Alpha channel manipulation in the LUT.
                    # 255 = Fully Opaque (Selected)
                    # 200 = Slight Transparency (Unselected, lets terrain texture show through)
                    alpha = 255 if dense_id in self.multi_select_dense_ids else 200
                    
                    self.lut_data[dense_id] = [color[0], color[1], color[2], alpha]

    def _update_selection_texture(self):
        """
        Optimized partial update for the LUT when only selection changes.
        """
        # 1. Revert old selection to standard opacity
        for idx in self.prev_multi_select_dense_ids:
            if idx < len(self.lut_data) and idx != 0: 
                if self.lut_data[idx, 3] > 0:
                    self.lut_data[idx, 3] = 200

        # 2. Set new selection to full opacity
        for idx in self.multi_select_dense_ids:
            if idx < len(self.lut_data) and idx != 0: 
                if self.lut_data[idx, 3] > 0:
                    self.lut_data[idx, 3] = 255

        self.prev_multi_select_dense_ids = self.multi_select_dense_ids.copy()
        self.lookup_texture.write(self.lut_data.tobytes())

    def set_highlight(self, real_region_ids: List[int]):
        """
        Updates the visual highlight state for specific regions.
        """
        if not real_region_ids:
            self.clear_highlight()
            return

        valid_dense_ids = []
        for rid in real_region_ids:
            if rid in self.real_to_dense:
                valid_dense_ids.append(self.real_to_dense[rid])

        if not valid_dense_ids:
            return

        # Case 1: Single Selection (Use Shader Uniform)
        if len(valid_dense_ids) == 1:
            self.single_select_dense_id = valid_dense_ids[0]
            if self.multi_select_dense_ids:
                self.multi_select_dense_ids = set()
                self._update_selection_texture()
        
        # Case 2: Multi-selection (Use LUT modification)
        else:
            self.single_select_dense_id = -1
            new_set = set(valid_dense_ids)
            if new_set != self.multi_select_dense_ids:
                self.multi_select_dense_ids = new_set
                self._update_selection_texture()

    def clear_highlight(self):
        self.single_select_dense_id = -1
        if self.multi_select_dense_ids:
            self.multi_select_dense_ids = set()
            self._update_selection_texture()

    def draw(self, mode: str = "terrain"):
        """
        Args:
            mode: 'terrain' (default) or 'overlay' (any colored map mode).
        """
        # 1. Draw Terrain Base
        if self.terrain_list:
            self.terrain_list.draw()

        # Optimization: Early exit if just terrain and no selection
        if mode == "terrain" and self.single_select_dense_id == -1 and not self.multi_select_dense_ids:
            return

        # 2. GL State Setup
        self.ctx.enable(self.ctx.BLEND)
        self.ctx.blend_func = self.ctx.BLEND_DEFAULT
        
        self.map_texture.use(0)
        self.lookup_texture.use(1)
        
        self.program['u_view'] = self.window.ctx.view_matrix
        self.program['u_projection'] = self.window.ctx.projection_matrix
        self.program['u_selected_id'] = int(self.single_select_dense_id)
        
        # --- FIX STARTS HERE ---
        # Allow both "overlay" (generic) and "political" (legacy/specific) to trigger the coloring shader
        if mode in ("overlay", "political"):
            self.program['u_overlay_mode'] = 1
            self.program['u_opacity'] = 0.9
        else:
            # Selection only (Terrain mode)
            self.program['u_overlay_mode'] = 0
            self.program['u_opacity'] = 1.0 
        # --- FIX ENDS HERE ---

        # 4. Draw Quad
        self.quad_geometry.render(self.program)

    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> int:
        img_y = int(self.height - world_y)
        if not (0 <= world_x < self.width and 0 <= img_y < self.height):
            return 0
        return self.map_data.get_region_id(int(world_x), img_y)