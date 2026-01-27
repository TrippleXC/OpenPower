import polars as pl
import rtoml
from pathlib import Path
import sys

# Paths are resolved relative to the script's parent to ensure 
# portability regardless of where the python process is invoked.
PROJECT_ROOT = Path(__file__).parent.parent
MODULES_DIR = PROJECT_ROOT / "modules"
OUTPUT_FILE = PROJECT_ROOT / "DATA_SCHEMA.md"

def get_polars_type_name(dtype):
    """
    Converts a Polars DataType object into a clean, readable string 
    for the Markdown report.
    """
    return str(dtype).replace("DataType(", "").replace(")", "")

def analyze_tsv(file_path: Path) -> str:
    """
    Parses a TSV file to extract its column schema and a sample data row.
    """
    try:
        # We only read a few rows to minimize memory overhead.
        # schema_overrides is used for 'hex' because automated inference 
        # might incorrectly treat hex strings as integers or nulls.
        df = pl.read_csv(
            file_path, 
            separator="\t", 
            n_rows=5, 
            ignore_errors=True,
            infer_schema_length=1000,
            schema_overrides={"hex": pl.String}
        )
        
        output = []
        output.append(f"### 📄 TSV: `{file_path.relative_to(PROJECT_ROOT)}`")
        output.append(f"**Columns:** {len(df.columns)}")
        output.append("\n| Column Name | Type | Example Value |")
        output.append("|---|---|---|")
        
        row = df.row(0, named=True) if not df.is_empty() else {}
        
        for col_name, dtype in df.schema.items():
            example = str(row.get(col_name, "N/A"))
            # Truncate overly long strings to keep the Markdown table scannable.
            if len(example) > 50: example = example[:47] + "..."
            output.append(f"| `{col_name}` | {get_polars_type_name(dtype)} | `{example}` |")
            
        return "\n".join(output)
    except Exception as e:
        return f"### ❌ Error reading `{file_path.name}`: {e}"

def analyze_toml(file_path: Path) -> str:
    """
    Analyzes TOML files to determine if they follow the 'Matrix' or 'List' strategy.
    This helps the AI understand the relational structure of the config.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = rtoml.load(f)
            
        output = []
        output.append(f"### ⚙️ TOML: `{file_path.relative_to(PROJECT_ROOT)}`")
        
        if not data:
            output.append("_Empty file_")
            return "\n".join(output)

        output.append("```toml")
        
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                # 'List Strategy': Often used for entity definitions like units or buildings.
                first_item = value[0]
                if isinstance(first_item, dict):
                    output.append(f"[[{key}]] # List of Objects")
                    for sub_k, sub_v in first_item.items():
                        output.append(f"  {sub_k} = {type(sub_v).__name__} (e.g. {str(sub_v)[:20]})")
                else:
                    output.append(f"{key} = List[{type(first_item).__name__}]")
                    
            elif isinstance(value, dict):
                 # 'Matrix Strategy': Used for relationships like diplomacy or trade rates.
                 output.append(f"[{key}] # Dictionary/Matrix")
                 first_k = next(iter(value))
                 output.append(f"  {first_k} = ...")
            else:
                # Simple global constants.
                output.append(f"{key} = {type(value).__name__}")
        
        output.append("```")
        return "\n".join(output)

    except Exception as e:
        return f"### ❌ Error reading `{file_path.name}`: {e}"

def generate_report():
    """
    Orchestrates the scanning process across all game modules and 
    consolidates results into a single Markdown file.
    """
    print(f"Scanning modules in: {MODULES_DIR}...")
    
    report_lines = ["# 🗃️ OpenPower Data Schema Report", ""]
    report_lines.append(f"> Auto-generated snapshot of data structures.\n")
    
    # We use rglob to find data deep within nested module structures.
    data_files = sorted(list(MODULES_DIR.rglob("*")))
    
    current_mod = ""
    
    for p in data_files:
        if p.is_dir(): continue
        
        # Group entries by module name to provide a clear hierarchy in the report.
        mod_name = p.relative_to(MODULES_DIR).parts[0]
        if mod_name != current_mod:
            current_mod = mod_name
            report_lines.append(f"\n## 📦 Module: `{mod_name}`\n---")

        if p.suffix == ".tsv":
            report_lines.append(analyze_tsv(p))
            report_lines.append("")
        elif p.suffix == ".toml" and p.name != "mod.toml": 
            # We ignore 'mod.toml' as it contains metadata, not game data.
            report_lines.append(analyze_toml(p))
            report_lines.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"✅ Schema generated at: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()