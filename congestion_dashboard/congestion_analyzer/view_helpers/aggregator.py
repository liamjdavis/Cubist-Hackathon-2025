import pandas as pd

def perform_aggregations(df):
    """Performs hourly, daily, and monthly aggregations on the DataFrame."""
    aggregations = {'hourly': pd.DataFrame(), 'daily': pd.DataFrame(), 'monthly': pd.DataFrame()}
    
    if df.empty:
        print("[Aggregator] Input DataFrame is empty. Skipping aggregations.")
        return aggregations

    print(f"[Aggregator] Original DataFrame size for aggregation: {len(df)} records")

    # Ensure crz_entries exists and is numeric for aggregation
    if 'crz_entries' not in df.columns:
         print("[Aggregator] Error: 'crz_entries' column required for aggregation is missing. Returning empty aggregations.")
         return aggregations
    df['crz_entries'] = pd.to_numeric(df['crz_entries'], errors='coerce').fillna(0)
    print("[Aggregator] Ensured 'crz_entries' is numeric.")

    # Define required columns for each aggregation level
    hourly_cols = ['detection_region', 'vehicle_class', 'hour_of_day']
    daily_cols = ['detection_region', 'vehicle_class', 'day_of_week', 'day_of_week_int']
    monthly_cols = ['detection_region', 'vehicle_class', 'month_year'] # month_year is derived in data_fetcher

    # --- Hourly Aggregation ---
    print("[Aggregator] Performing hourly aggregation...")
    if all(col in df.columns for col in hourly_cols):
        try:
            hourly_agg = df.groupby(hourly_cols, observed=False)['crz_entries'].sum().reset_index()
            aggregations['hourly'] = hourly_agg
            print(f"[Aggregator] Hourly aggregation completed: {len(hourly_agg)} records")
        except Exception as e:
             print(f"[Aggregator] Error during hourly aggregation: {e}")
    else:
        missing = [c for c in hourly_cols if c not in df.columns]
        print(f"[Aggregator] Skipping hourly aggregation due to missing columns: {missing}")

    # --- Daily Aggregation ---
    print("[Aggregator] Performing daily aggregation...")
    if all(col in df.columns for col in daily_cols):
        try:
            daily_agg = df.groupby(daily_cols, observed=False)['crz_entries'].sum().reset_index()
            # Optionally sort by day_of_week_int if needed here
            # daily_agg = daily_agg.sort_values('day_of_week_int')
            aggregations['daily'] = daily_agg
            print(f"[Aggregator] Daily aggregation completed: {len(daily_agg)} records")
        except Exception as e:
            print(f"[Aggregator] Error during daily aggregation: {e}")
    else:
        missing = [c for c in daily_cols if c not in df.columns]
        print(f"[Aggregator] Skipping daily aggregation due to missing columns: {missing}")

    # --- Monthly Aggregation ---
    print("[Aggregator] Performing monthly aggregation...")
    if all(col in df.columns for col in monthly_cols):
         try:
             monthly_agg = df.groupby(monthly_cols, observed=False)['crz_entries'].sum().reset_index()
             # Optionally sort by month_year if needed here
             # monthly_agg = monthly_agg.sort_values('month_year')
             aggregations['monthly'] = monthly_agg
             print(f"[Aggregator] Monthly aggregation completed: {len(monthly_agg)} records")
         except Exception as e:
             print(f"[Aggregator] Error during monthly aggregation: {e}")
    else:
        missing = [c for c in monthly_cols if c not in df.columns]
        print(f"[Aggregator] Skipping monthly aggregation due to missing columns: {missing}")

    return aggregations 