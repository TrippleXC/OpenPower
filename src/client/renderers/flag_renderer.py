import arcade
import arcade.gl
from pathlib import Path
from typing import Dict, Optional, Any
from PIL import Image

class FlagTexture:
    """
    Wrapper to hold both the GL Object (to prevent Garbage Collection) 
    and the ID for ImGui.
    """
    def __init__(self, gl_obj: Any, gl_id: int, width: int, height: int):
        self.gl_obj = gl_obj  # CRITICAL: Holding this prevents the GPU from deleting the texture
        self.gl_id = gl_id
        self.width = width
        self.height = height

class FlagRenderer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FlagRenderer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        
        current_path = Path(__file__).resolve()
        self.project_root = current_path
        for parent in current_path.parents:
            if (parent / "modules").exists():
                self.project_root = parent
                break
        
        self.flags_dir = self.project_root / "modules" / "base" / "assets" / "flags"
        self._cache: Dict[str, Optional[FlagTexture]] = {}
        self._fallback_tag = "XXX"
        self._initialized = True
        
        self._emergency_texture = self._create_emergency_texture()
        print(f"[FlagRenderer] Memory Persistence Mode. Flags at: {self.flags_dir}")

    def _create_emergency_texture(self) -> Optional[FlagTexture]:
        try:
            img = Image.new('RGBA', (32, 32), (255, 0, 255, 255))
            return self._upload_to_gpu(img, "EMERGENCY")
        except Exception:
            return None

    def _upload_to_gpu(self, image: Image.Image, label: str) -> Optional[FlagTexture]:
        """
        Uploads PIL image and returns a wrapper that PROTECTS the texture from GC.
        """
        try:
            window = arcade.get_window()
            ctx = window.ctx
            
            # 1. Create Texture
            gl_texture = ctx.texture(
                (image.width, image.height),
                components=4,
                data=image.tobytes()
            )
            
            # 2. Configure for ImGui (No Mipmaps)
            gl_texture.filter = (ctx.LINEAR, ctx.LINEAR)
            
            # 3. Extract ID robustly
            raw_glo = getattr(gl_texture, "glo", None)
            tex_id = 0
            
            if raw_glo is not None:
                if hasattr(raw_glo, "glo_id"): 
                    tex_id = int(raw_glo.glo_id)
                elif hasattr(raw_glo, "value"): 
                    tex_id = int(raw_glo.value)
                else:
                    tex_id = int(raw_glo)

            if tex_id == 0:
                return None
            
            # We return the gl_texture object itself so it stays alive in our self._cache
            return FlagTexture(gl_texture, tex_id, image.width, image.height)

        except Exception as e:
            print(f"[FlagRenderer] GPU Upload Error ({label}): {e}")
            return None

    def get_texture(self, tag: str) -> Optional[FlagTexture]:
        if tag in self._cache:
            return self._cache[tag]

        clean_tag = tag.strip()
        flag_path = self.flags_dir / f"{clean_tag}.png"
        
        if not flag_path.exists():
            lower_path = self.flags_dir / f"{clean_tag.lower()}.png"
            if lower_path.exists(): flag_path = lower_path
            else: flag_path = self.flags_dir / f"{self._fallback_tag}.png"

        if not flag_path.exists():
            return self._emergency_texture

        try:
            with Image.open(flag_path) as img:
                img = img.convert("RGBA")
                texture = self._upload_to_gpu(img, tag)
                if texture:
                    self._cache[tag] = texture
                    return texture
                return self._emergency_texture
        except Exception as e:
            print(f"[FlagRenderer] Load Error {tag}: {e}")
            return self._emergency_texture

    def clear_cache(self):
        self._cache.clear()