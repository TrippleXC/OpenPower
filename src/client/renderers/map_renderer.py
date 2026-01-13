import arcade
import arcade.gl
import numpy as np
from array import array
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from pyglet import gl

from src.core.map_data import RegionMapData
from src.client.shader_registry import ShaderRegistry

class MapRenderer:
    def __init__(self, 
                 map_data: RegionMapData, 
                 map_img_path: Path, 
                 terrain_img_path: Path):
        
        self.window = arcade.get_window()
        self.ctx = self.window.ctx
        self.map_data = map_data
        self.width = map_data.width
        self.height = map_data.height
        
        self.selected_id = -1
        self.lut_dim = 4096 

        # State cache for country highlighting
        self._cached_ownership: Dict[int, str] = {}
        self._cached_colors: Dict[str, Tuple[int, int, int]] = {}
        self._current_highlight_tag: Optional[str] = None

        self.terrain_sprite: Optional[arcade.Sprite] = None
        self._init_resources(terrain_img_path)
        self._init_glsl()

    def _init_resources(self, terrain_path: Path):
        if terrain_path.exists():
            self.terrain_sprite = arcade.Sprite(terrain_path)
            self.terrain_sprite.width = self.width
            self.terrain_sprite.height = self.height
            self.terrain_sprite.center_x = self.width / 2
            self.terrain_sprite.center_y = self.height / 2

        # Main Texture Generation
        b = (self.map_data.packed_map & 0xFF).astype(np.uint8)
        g = ((self.map_data.packed_map >> 8) & 0xFF).astype(np.uint8)
        r = ((self.map_data.packed_map >> 16) & 0xFF).astype(np.uint8)
        rgb_data = np.dstack((r, g, b))
        rgb_data = np.flipud(rgb_data)

        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

        self.map_texture = self.ctx.texture(
            (self.width, self.height),
            components=3,
            data=rgb_data.tobytes(),
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )
        
        self.lookup_texture = self.ctx.texture(
            (self.lut_dim, self.lut_dim),
            components=4,
            filter=(self.ctx.NEAREST, self.ctx.NEAREST)
        )

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

    def update_political_layer(self, region_ownership: Dict[int, str], country_colors: Dict[str, Tuple[int, int, int]]):
        """Saves data for potential redraws and updates GPU."""
        self._cached_ownership = region_ownership
        self._cached_colors = country_colors
        self._upload_lut(highlight_tag=self._current_highlight_tag)

    def set_country_highlight(self, tag: str):
        """Highlights all regions belonging to a specific country tag."""
        self._current_highlight_tag = tag
        self.selected_id = -1 # Disable white outline for single region
        self._upload_lut(highlight_tag=tag)

    def clear_country_highlight(self):
        """Restores map to normal state."""
        self._current_highlight_tag = None
        self._upload_lut(highlight_tag=None)

    def _upload_lut(self, highlight_tag: Optional[str] = None):
        """Writes data to the Lookup Texture. Dims colors not matching highlight_tag."""
        lut_data = np.full((self.lut_dim * self.lut_dim, 4), 0, dtype=np.uint8)
        lut_data[:, 3] = 255 

        for rid, tag in self._cached_ownership.items():
            if rid < len(lut_data):
                color = self._cached_colors.get(tag, (100, 100, 100))
                
                if highlight_tag is not None:
                    if tag == highlight_tag:
                        # Focused country: Full Brightness
                        lut_data[rid] = [color[0], color[1], color[2], 255]
                    else:
                        # Background countries: Dimmed
                        lut_data[rid] = [int(color[0]*0.25), int(color[1]*0.25), int(color[2]*0.25), 255]
                else:
                    # Default: Normal Brightness
                    lut_data[rid] = [color[0], color[1], color[2], 255]

        self.lookup_texture.write(lut_data.tobytes())

    def draw(self, mode: str = "terrain"):
        if self.terrain_sprite and mode == "terrain":
            self.terrain_sprite.draw()

        self.ctx.enable(self.ctx.BLEND)
        self.map_texture.use(0)
        self.lookup_texture.use(1)
        
        self.program['u_view'] = self.window.ctx.view_matrix
        self.program['u_projection'] = self.window.ctx.projection_matrix
        self.program['u_selected_id'] = int(self.selected_id)
        
        if mode == "political":
            self.program['u_overlay_mode'] = 1
            self.program['u_opacity'] = 0.9
        else:
            self.program['u_overlay_mode'] = 0
            self.program['u_opacity'] = 1.0

        self.quad_geometry.render(self.program)

    def set_highlight(self, region_ids: List[int]):
        if not region_ids:
            self.selected_id = -1
        else:
            self.selected_id = region_ids[0]

    def get_region_id_at_world_pos(self, world_x: float, world_y: float) -> int:
        img_y = int(self.height - world_y)
        if not (0 <= world_x < self.width and 0 <= img_y < self.height):
            return 0
        return self.map_data.get_region_id(int(world_x), img_y)