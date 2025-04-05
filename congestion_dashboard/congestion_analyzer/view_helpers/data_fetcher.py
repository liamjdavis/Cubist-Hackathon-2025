import pandas as pd
from django.db.models import F, Func, Value
from django.db.models.functions import Cast # If needed for date casting
from django.db.models import CharField
from ..models import VehicleEntry # Use relative import

def get_vehicle_data():
    """
    Fetches vehicle entries from the database, deriving month_year efficiently,
    and converts to a DataFrame.
    """
    print("[Data Fetcher] Querying database and deriving month_year...")

    # Define the formatting function using Func
    # This example uses TO_CHAR suitable for PostgreSQL/Oracle.
    # Adjust 'function' and 'template' based on your specific database.
    # If 'toll_date' might not be a date type in DB, cast it first: Cast('toll_date', DateField())
    month_year_func = Func(
        F('toll_date'),
        Value('%Y-%m'),      # Use SQLite strftime format
        function='strftime',  # Use SQLite strftime function
        output_field=CharField()
    )

    queryset = VehicleEntry.objects.annotate(
        month_year_str=month_year_func
    ).values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
        'detection_group', 'toll_week',
        'month_year_str' # Include the annotated value
    )

    # Use from_records for potentially better memory efficiency
    df = pd.DataFrame.from_records(queryset)
    print(f"[Data Fetcher] Fetched {len(df)} records.")

    if df.empty:
        print("[Data Fetcher] DataFrame is empty.")
    else:
        # Rename the database-generated column for consistency
        df.rename(columns={'month_year_str': 'month_year'}, inplace=True)
        print("[Data Fetcher] 'month_year' derived during database query.")

        # Optional: Convert toll_date to datetime if needed elsewhere,
        # but the expensive month_year part is done.
        # df['toll_date'] = pd.to_datetime(df['toll_date'], errors='coerce')
        # print("[Data Fetcher] Converted 'toll_date' to datetime objects (optional).")

    return df 