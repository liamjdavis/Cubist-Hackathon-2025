import pandas as pd
from ..models import VehicleEntry # Use relative import

def get_vehicle_data():
    """Fetches all vehicle entries from the database and converts to a DataFrame."""
    print("[Data Fetcher] Querying database...")
    queryset = VehicleEntry.objects.all().values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
        'detection_group', 'toll_week'
    )
    df = pd.DataFrame(list(queryset))
    print(f"[Data Fetcher] Fetched {len(df)} records initially.")

    if not df.empty and 'toll_date' in df.columns:
        print("[Data Fetcher] Processing 'toll_date' column...")
        # Ensure toll_date is datetime type, coerce errors to NaT
        df['toll_date'] = pd.to_datetime(df['toll_date'], errors='coerce') 
        
        # Check for NaT values created by coercion
        nat_count = df['toll_date'].isna().sum()
        if nat_count > 0:
            print(f"[Data Fetcher] Warning: {nat_count} invalid date formats found in 'toll_date'. These rows will not have 'month_year'.")

        # Add month_year for aggregation only where toll_date is valid
        df['month_year'] = df['toll_date'].dt.strftime('%Y-%m') 
        print("[Data Fetcher] 'month_year' derived from 'toll_date'.")
    elif df.empty:
        print("[Data Fetcher] DataFrame is empty.")
    else: # df not empty but toll_date missing
        print("[Data Fetcher] Warning: 'toll_date' column not found in fetched data.")

    return df 