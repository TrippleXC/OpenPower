import ctypes
from pathlib import Path
from imgui_bundle import imgui

class FontLoader:
    """
    Manages loading of TrueType fonts using direct memory manipulation 
    to bypass binding limitations.
    """
    
    # Keep references to arrays so Garbage Collector doesn't destroy them
    _keep_alive_storage = []

    @staticmethod
    def load_primary_font(io, font_path: Path, size_pixels: float = 10.0, load_cjk: bool = False):
        if not font_path.exists():
            print(f"[FontLoader] Warning: Font not found at {font_path}. Using default.")
            return

        print(f"[FontLoader] Loading font: {font_path.name} ({size_pixels}px)")
        
        # 1. Clear existing fonts
        io.fonts.clear()

        # 2. Prepare Ranges (Latin + Cyrillic) via ctypes
        # This creates a raw C-style array of unsigned shorts (16-bit)
        # 0x0020-0x00FF: Latin, 0x0400-0x052F: Cyrillic, 0: Terminator
        ranges_list = [
            0x0020, 0x00FF, 
            0x0400, 0x052F, 
            0 
        ]
        
        RangeArrayType = ctypes.c_ushort * len(ranges_list)
        c_ranges = RangeArrayType(*ranges_list)
        
        # Store in list to prevent Garbage Collection
        FontLoader._keep_alive_storage.append(c_ranges)
        
        # Get raw memory address (int)
        ranges_ptr = ctypes.addressof(c_ranges)

        # 3. Setup Config
        font_cfg = imgui.ImFontConfig()
        font_cfg.oversample_h = 1
        font_cfg.oversample_v = 1
        font_cfg.pixel_snap_h = True
        
        # --- THE FIX ---
        # We attempt to set the pointer. We use # type: ignore because 
        # Pylance stubs often miss these pointer fields in auto-generated bindings.
        try:
            # Try snake_case (standard for imgui_bundle)
            font_cfg.glyph_ranges = ranges_ptr # type: ignore
        except AttributeError:
            try:
                # Try PascalCase (raw C++ mapping)
                font_cfg.GlyphRanges = ranges_ptr # type: ignore
            except AttributeError:
                print("[FontLoader] Warning: Could not set glyph_ranges on ImFontConfig.")

        # 4. Load Base Font
        # Strictly use the 3-argument signature
        io.fonts.add_font_from_file_ttf(
            str(font_path), 
            size_pixels, 
            font_cfg
        )

        # 5. Optional CJK Merge
        if load_cjk:
            try:
                merge_cfg = imgui.ImFontConfig()
                merge_cfg.merge_mode = True
                merge_cfg.pixel_snap_h = True
                
                # Try to get CJK ranges from IO (sometimes exposed there)
                # or skip if unavailable.
                if hasattr(io.fonts, "get_glyph_ranges_chinese_full"):
                    cjk_ranges = io.fonts.get_glyph_ranges_chinese_full()
                    merge_cfg.glyph_ranges = cjk_ranges # type: ignore
                    
                    io.fonts.add_font_from_file_ttf(
                        str(font_path),
                        size_pixels,
                        merge_cfg
                    )
                    print("[FontLoader] CJK Glyphs merged.")
            except Exception as e:
                print(f"[FontLoader] Skipped CJK: {e}")

        print("[FontLoader] Font loaded successfully.")