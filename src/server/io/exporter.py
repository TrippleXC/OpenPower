import polars as pl
from pathlib import Path
from src.server.state import GameState

class DataExporter:
    """
    Responsible for persisting the GameState back to human-readable files (TSV/TOML).
    Used primarily by the Editor Mode to save changes.
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        # TODO: Make this path dynamic based on the active mod.
        self.data_dir = root_dir / "modules" / "base" / "data"

    def save_regions(self, state: GameState):
        """
        Exports the 'regions' table back to TSV format.
        
        Challenge:
            The Engine uses an optimized Int32 'color_id' for rendering.
            The TSV file needs a Hex string '#RRGGBB' for humans.
            We must reverse the bitwise packing done in Loader.
        """
        print("[DataExporter] Saving regions to disk...")
        df = state.get_table("regions")

        # 1. Reverse the ID Packing: Int32 -> R, G, B
        # Formula: B = ID & 255, G = (ID >> 8) & 255, R = (ID >> 16) & 255
        export_df = df.with_columns([
            ((pl.col("color_id") >> 16) & 0xFF).alias("_r"),
            ((pl.col("color_id") >> 8) & 0xFF).alias("_g"),
            (pl.col("color_id") & 0xFF).alias("_b")
        ])

        # 2. Format as Hex String (#RRGGBB)
        # We use a custom map function because Polars string formatting is still evolving.
        # This is slightly slower than pure SIMD but acceptable for saving (IO bound).
        def to_hex(r, g, b):
            return f"#{r:02x}{g:02x}{b:02x}"

        # Combine columns into a struct to map over them row-by-row
        export_df = export_df.with_columns(
            pl.struct(["_r", "_g", "_b"])
            .map_elements(lambda x: to_hex(x["_r"], x["_g"], x["_b"]), return_dtype=pl.Utf8)
            .alias("hex")
        )

        # 3. Cleanup & Write
        # Remove engine-specific columns before writing
        final_df = export_df.drop(["color_id", "_r", "_g", "_b"])
        
        # Ensure 'id' is the first column for readability
        final_df = final_df.select(["id", "hex", "name", "owner", "type", pl.exclude("id", "hex", "name", "owner", "type")])

        target_path = self.data_dir / "map" / "regions.tsv"
        final_df.write_csv(target_path, separator="\t")
        print(f"[DataExporter] Saved {len(final_df)} regions to {target_path}")