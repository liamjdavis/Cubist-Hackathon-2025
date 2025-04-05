import pandas as pd

def calculate_base_stats(df):
    """Calculates base statistics from the vehicle data DataFrame."""
    print("[Stats Calculator] Calculating base statistics...")
    if df.empty:
        print("[Stats Calculator] Input DataFrame is empty. Returning zero stats.")
        return 0, [], 0 # total_entries, region_data, total_volume

    total_entries = len(df)
    print(f"[Stats Calculator] Total entries (rows): {total_entries}")
    
    # Ensure 'crz_entries' exists and is numeric, coercing errors to NaN, then filling NaN with 0
    if 'crz_entries' in df.columns:
        df['crz_entries'] = pd.to_numeric(df['crz_entries'], errors='coerce').fillna(0)
        total_volume = df['crz_entries'].sum()
        print(f"[Stats Calculator] Total volume (sum of crz_entries): {total_volume}")
    else:
        print("[Stats Calculator] Warning: 'crz_entries' column not found. Total volume set to 0.")
        total_volume = 0

    # Create region summary, handle potential missing 'detection_region'
    if 'detection_region' in df.columns and 'crz_entries' in df.columns:
        print("[Stats Calculator] Calculating region summary...")
        region_summary = df.groupby('detection_region', observed=False)['crz_entries'].sum().reset_index()
        region_summary = region_summary.rename(columns={'crz_entries': 'count'})
        region_summary = region_summary.sort_values('count', ascending=False)
        region_data = region_summary.to_dict('records')
        print(f"[Stats Calculator] Region summary calculated for {len(region_data)} regions.")
    else:
        region_data = []
        missing_cols = [col for col in ['detection_region', 'crz_entries'] if col not in df.columns]
        print(f"[Stats Calculator] Warning: Cannot calculate region summary due to missing columns: {missing_cols}. Region data set to empty list.")

    return total_entries, region_data, total_volume 