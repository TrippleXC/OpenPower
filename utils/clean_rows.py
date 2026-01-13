import pandas as pd
from pathlib import Path

def get_reference_ids(reference_file: Path, column_name: str = 'id') -> set:
    """
    Extracts unique IDs from the master file.
    Using a set ensures O(1) complexity for membership tests.
    """
    try:
        df = pd.read_csv(reference_file, sep='\t')
        # Dropping duplicates at the source to keep the set minimal
        return set(df[column_name].dropna().unique())
    except Exception as e:
        print(f"Critical Error: Could not read master file {reference_file}. {e}")
        return set()

def sync_file_with_ids(file_path: Path, valid_ids: set, column_name: str):
    """
    Overwrites the file with rows that match the reference IDs.
    """
    try:
        df = pd.read_csv(file_path, sep='\t')
        
        # Filter based on composition: we keep only what's in our valid set
        filtered_df = df[df[column_name].isin(valid_ids)]
        
        rows_removed = len(df) - len(filtered_df)
        
        if rows_removed > 0:
            filtered_df.to_csv(file_path, sep='\t', index=False)
            print(f"Cleaned: {file_path.name} (-{rows_removed} rows)")
        else:
            print(f"Skipped: {file_path.name} (No invalid IDs found)")
            
    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")

def main():
    # Configuration
    base_path = Path(".") 
    master_filename = "countries.tsv"
    target_column = "id"

    # 1. Prepare reference data
    master_file_path = base_path / master_filename
    valid_ids = get_reference_ids(master_file_path, target_column)

    if not valid_ids:
        return

    # 2. Discover and process all TSV files (Modular search)
    # This includes all .tsv files except the master itself
    tsv_files = [
        f for f in base_path.glob("*.tsv") 
        if f.name != master_filename
    ]

    print(f"Found {len(tsv_files)} files to process...")

    for tsv_file in tsv_files:
        sync_file_with_ids(tsv_file, valid_ids, target_column)

if __name__ == "__main__":
    main()