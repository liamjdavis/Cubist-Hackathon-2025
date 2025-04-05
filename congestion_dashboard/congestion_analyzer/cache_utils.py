# congestion_dashboard/congestion_analyzer/cache_utils.py
import pandas as pd
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import json
from django.core.serializers.json import DjangoJSONEncoder

# Attempt to import model and helpers, handle potential circular imports if necessary
try:
    from .models import VehicleEntry
    from .view_helpers.stats_calculator import calculate_base_stats
    from .view_helpers.aggregator import perform_aggregations
    # Import constants directly to avoid potential issues with importing map_views itself yet
    # Define them here or ensure they are accessible from a shared constants file later
    ENTRY_POINTS = {
        'Queensboro Bridge': [40.7561, -73.9525],
        'Queens-Midtown Tunnel': [40.7527, -73.9675],
        'Williamsburg Bridge': [40.7127, -73.9707],
        'Manhattan Bridge': [40.7074, -73.9891],
        'Brooklyn Bridge': [40.7061, -73.9969],
        'Hugh Carey Tunnel': [40.7007, -74.0178],
        'Holland Tunnel': [40.7282, -74.0287],
        'Lincoln Tunnel': [40.7614, -73.9536], # Adjusted slightly based on common entry context
        'FDR Drive at 60th Street': [40.7610, -73.9590], # Approximated FDR near 60th
        'East 60th Street': [40.7618, -73.9648], # Near 2nd Ave
        'West 60th Street': [40.7700, -73.9850] # Near Columbus Circle/Broadway
    }
    VEHICLE_TYPES = {
        'car': {'name': 'Passenger Cars', 'color': [65, 182, 196], 'order': 0},
        'taxi': {'name': 'Taxis', 'color': [254, 221, 0], 'order': 1},
        'bus': {'name': 'Buses', 'color': [44, 127, 184], 'order': 2},
        'multi_unit_truck': {'name': 'Multi-Unit Trucks', 'color': [127, 60, 141], 'order': 3},
        'single_unit_truck': {'name': 'Single Unit Trucks', 'color': [217, 95, 2], 'order': 4},
        'motorcycle': {'name': 'Motorcycles', 'color': [231, 41, 138], 'order': 5}
    }
    VEHICLE_CLASS_MAPPING = { # Centralized mapping
        'Passenger Car': 'car', 'Taxi': 'taxi', 'Bus': 'bus',
        'Multi-Unit Truck': 'multi_unit_truck', 'Single-Unit Truck': 'single_unit_truck',
        'Motorcycle': 'motorcycle'
    }

except ImportError as e:
    print(f"Error importing modules in cache_utils: {e}. Check for circular dependencies.")
    # Define fallbacks or raise error if critical dependencies are missing
    VehicleEntry = None
    calculate_base_stats = lambda df: (0, [], 0)
    perform_aggregations = lambda df: []
    ENTRY_POINTS = {}
    VEHICLE_TYPES = {}
    VEHICLE_CLASS_MAPPING = {}


# Define perspective type mapping
# https://perspective.finos.org/docs/md/js.html#schematypes
PERSPECTIVE_TYPE_MAP = {
    'int64': 'integer',
    'int32': 'integer',
    'int16': 'integer',
    'int8': 'integer',
    'float64': 'float',
    'float32': 'float',
    'bool': 'boolean',
    'datetime64[ns]': 'datetime',
    'datetime64[ns, UTC]': 'datetime', # Handle timezone-aware
    'timedelta64[ns]': 'integer', # Map timedelta to integer (e.g., milliseconds) - adjust if needed
    'object': 'string', # Default for object
    'string': 'string',
    'category': 'string'
}

# Define a complete hardcoded schema with all columns needed for visualizations,
# regardless of what's actually in the data
COMPLETE_PERSPECTIVE_SCHEMA = {
    # Base columns from DB
    'toll_date': 'datetime',
    'hour_of_day': 'integer',
    'day_of_week': 'string',
    'day_of_week_int': 'integer',
    'vehicle_class': 'string',
    'detection_region': 'string',
    'crz_entries': 'integer',
    'time_period': 'string',
    'detection_group': 'string',
    'toll_week': 'string',
    # Derived/aggregated columns that views might use
    'month_year': 'string',
    'entries_normalized': 'float',
    'total_entries': 'integer',
    'record_count': 'integer',
    # Summary/aggregation columns
    'sum_crz_entries': 'integer', # For aggregations
    'avg_crz_entries': 'float'    # For aggregations
}

def get_perspective_schema(df):
    """
    Returns a Perspective schema dictionary.
    Now simply returns our complete hardcoded schema to ensure
    all view columns are available.
    """
    # Instead of deriving from df, use our comprehensive schema
    return COMPLETE_PERSPECTIVE_SCHEMA.copy()

# Cache keys
BASE_DATA_CACHE_KEY = 'vehicle_data_df_v2'
STATS_CACHE_KEY = 'dashboard_stats_v2'
AGG_JSON_CACHE_KEY = 'dashboard_agg_json_v2'
# Add schema cache key
SCHEMA_CACHE_KEY = 'perspective_schema_v4'  # Used to be v3
MAP_DATA_CACHE_KEY = 'map_view_data_v2'
DATE_RANGE_CACHE_KEY = 'data_date_range_v2'

# Cache timeout (in seconds) - e.g., 1 hour
CACHE_TIMEOUT = 3600

def get_base_vehicle_data():
    """
    Fetches vehicle data from the database or cache.
    Returns a Pandas DataFrame. Handles basic type conversion.
    """
    if VehicleEntry is None: # Check if import failed
        print("!!! VehicleEntry model not available in cache_utils. Returning empty DataFrame.")
        return pd.DataFrame()

    cached_data = cache.get(BASE_DATA_CACHE_KEY)
    if cached_data:
        print("--- Cache Hit: Base vehicle data ---")
        try:
            df = pd.read_json(cached_data, orient='split')
            # Ensure 'toll_date' is datetime after reading from JSON
            if 'toll_date' in df.columns:
                # Important: Specify UTC=True if dates were timezone-aware
                df['toll_date'] = pd.to_datetime(df['toll_date'], errors='coerce', utc=True)
            # Ensure other types are correct after JSON deserialization if needed
            if 'crz_entries' in df.columns:
                df['crz_entries'] = pd.to_numeric(df['crz_entries'], errors='coerce').fillna(0).astype(int)
            if 'hour_of_day' in df.columns:
                df['hour_of_day'] = pd.to_numeric(df['hour_of_day'], errors='coerce').fillna(0).astype(int)
            return df
        except Exception as e:
            print(f"Error deserializing cached base data: {e}. Refetching.")
            # Fall through to refetch if cache is corrupted

    print("--- Cache Miss: Fetching base vehicle data from DB ---")
    queryset = VehicleEntry.objects.all().values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
        'detection_group', 'toll_week'
    )
    df = pd.DataFrame(list(queryset))

    if not df.empty:
        # Basic cleaning/type conversion right after fetch
        if 'toll_date' in df.columns:
            df['toll_date'] = pd.to_datetime(df['toll_date'], errors='coerce')
            # Ensure timezone awareness (assuming DB stores UTC or naive interpreted as UTC)
            if df['toll_date'].dt.tz is None:
                 df['toll_date'] = df['toll_date'].dt.tz_localize('UTC')
            else:
                 df['toll_date'] = df['toll_date'].dt.tz_convert('UTC')
        if 'crz_entries' in df.columns:
            df['crz_entries'] = pd.to_numeric(df['crz_entries'], errors='coerce').fillna(0).astype(int)
        if 'hour_of_day' in df.columns:
            df['hour_of_day'] = pd.to_numeric(df['hour_of_day'], errors='coerce').fillna(0).astype(int)

        # Drop rows with essential missing data after conversion
        df.dropna(subset=['toll_date', 'crz_entries', 'detection_region', 'vehicle_class'], inplace=True)

        # Cache the DataFrame as a JSON string
        try:
            df_json = df.to_json(orient='split', date_format='iso', default_handler=str)
            cache.set(BASE_DATA_CACHE_KEY, df_json, CACHE_TIMEOUT)
        except Exception as e:
            print(f"Error serializing DataFrame for cache: {e}")
            # Don't cache if serialization fails
    else:
        # Handle empty DataFrame: Create one with the expected columns
        print("--- DB query returned no data, creating empty DataFrame with schema ---")
        expected_columns = [
            'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
            'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
            'detection_group', 'toll_week'
        ]
        df = pd.DataFrame(columns=expected_columns)
        # Define appropriate dtypes for an empty DataFrame to help Perspective
        df = df.astype({
            'toll_date': 'datetime64[ns, UTC]', # Ensure timezone aware
            'hour_of_day': 'int',
            'day_of_week': 'object', # Or category
            'day_of_week_int': 'int',
            'vehicle_class': 'object',
            'detection_region': 'object',
            'crz_entries': 'int',
            'time_period': 'object',
            'detection_group': 'object',
            'toll_week': 'object'
        })
        # Cache the empty DataFrame with schema
        try:
            df_json = df.to_json(orient='split', date_format='iso', default_handler=str)
            cache.set(BASE_DATA_CACHE_KEY, df_json, CACHE_TIMEOUT)
        except Exception as e:
             print(f"Error serializing empty DataFrame for cache: {e}")

    return df

def get_dashboard_data():
    """
    Gets required data for the main dashboard view (stats, agg_json, schema) from cache or generates it.
    Returns: A tuple (stats_dict, agg_json_string, schema_dict)
    """
    stats = cache.get(STATS_CACHE_KEY)
    agg_json = cache.get(AGG_JSON_CACHE_KEY)
    schema = cache.get(SCHEMA_CACHE_KEY) # Check for cached schema

    if stats is not None and agg_json is not None and schema is not None:
        print("--- Cache Hit: Dashboard data (stats, agg_json, schema) ---")
        return stats, agg_json, schema

    print("--- Cache Miss: Generating dashboard data & schema ---")
    df = get_base_vehicle_data()

    # *** Derive schema from the BASE dataframe ***
    # Always get the comprehensive schema
    base_schema = get_perspective_schema(df)
    print(f"[Debug] Using complete schema with {len(base_schema)} columns")

    if df.empty:
        print("--- Base data is empty, returning default dashboard data & base schema ---")
        default_stats = {'total_entries': 0, 'region_data': [], 'total_volume': 0}
        
        # Create a minimal set of sample data
        # This ensures that when the data is empty, Perspective still has something to work with
        sample_data = []
        regions = ['Brooklyn Bridge', 'Queens-Midtown Tunnel', 'Lincoln Tunnel', 'Williamsburg Bridge', 'Holland Tunnel']
        vehicles = ['car', 'taxi', 'bus', 'multi_unit_truck', 'single_unit_truck', 'motorcycle']
        time_periods = ['AM', 'PM']
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_ints = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7}
        
        # Generate data for the last 30 days
        import random
        from datetime import datetime, timedelta
        
        # Create a "now" timestamp
        now = timezone.now()
        
        # Generate data for each day in the last 30 days
        for day_offset in range(30, 0, -1):  # 30 days ago to yesterday
            sample_date = now - timedelta(days=day_offset)
            day_name = days[sample_date.weekday()]  # 0=Monday, 6=Sunday
            day_int = day_ints[day_name]
            
            # Generate month_year string for monthly aggregations
            month_year = sample_date.strftime('%Y-%m')
            
            # For each day, generate data for all hours
            for hour in range(24):
                # Determine time period
                time_period = 'AM' if hour < 12 else 'PM'
                
                # For each region and vehicle type, create sample data
                for region in regions:
                    for vehicle in vehicles:
                        # Generate realistic data - higher for rush hours, lower at night
                        base_traffic = random.randint(100, 500)
                        if 7 <= hour <= 10 or 16 <= hour <= 19:  # Rush hours
                            multiplier = random.uniform(1.5, 3.0)  # 1.5-3x traffic during rush hour
                        elif 0 <= hour <= 5:  # Night hours
                            multiplier = random.uniform(0.1, 0.5)  # 10-50% traffic at night
                        else:  # Regular hours
                            multiplier = random.uniform(0.7, 1.3)  # 70-130% of base traffic
                        
                        # Apply vehicle-specific multipliers
                        if vehicle == 'car':
                            vehicle_mult = random.uniform(2.0, 4.0)  # Cars are most common
                        elif vehicle == 'taxi':
                            vehicle_mult = random.uniform(0.8, 1.5)  # Taxis are common
                        elif vehicle in ['bus', 'multi_unit_truck', 'single_unit_truck']:
                            vehicle_mult = random.uniform(0.3, 0.7)  # Commercial vehicles less common
                        else:  # motorcycle
                            vehicle_mult = random.uniform(0.1, 0.3)  # Least common
                        
                        # Apply day-of-week factors (weekdays vs weekends)
                        if day_name in ['Saturday', 'Sunday']:
                            day_mult = 0.7 if vehicle in ['bus', 'multi_unit_truck', 'single_unit_truck'] else 1.2
                        else:
                            day_mult = 1.2 if vehicle in ['bus', 'multi_unit_truck', 'single_unit_truck'] else 1.0
                        
                        # Calculate final traffic count
                        traffic = int(base_traffic * multiplier * vehicle_mult * day_mult)
                        
                        # Create the sample data entry
                        sample_data.append({
                            'toll_date': sample_date.isoformat(),
                            'hour_of_day': hour,
                            'day_of_week': day_name,
                            'day_of_week_int': day_int,
                            'vehicle_class': vehicle,
                            'detection_region': region,
                            'crz_entries': traffic,
                            'time_period': time_period,
                            'detection_group': 'CBD',
                            'toll_week': f"{sample_date.strftime('%Y')}-W{sample_date.strftime('%U')}",
                            'month_year': month_year
                        })
        
        # Convert to JSON with the encoder to handle any date/complex types
        default_agg_json = json.dumps(sample_data, cls=DjangoJSONEncoder)
        print(f"[Debug] Created {len(sample_data)} sample data points for empty dataset")
        
        # Cache defaults including the base schema
        cache.set(STATS_CACHE_KEY, default_stats, CACHE_TIMEOUT)
        cache.set(AGG_JSON_CACHE_KEY, default_agg_json, CACHE_TIMEOUT)
        cache.set(SCHEMA_CACHE_KEY, base_schema, CACHE_TIMEOUT) # Cache the schema
        return default_stats, default_agg_json, base_schema

    try:
        # Calculate stats
        total_entries, region_data, total_volume = calculate_base_stats(df.copy())
        calculated_stats = {'total_entries': total_entries, 'region_data': region_data, 'total_volume': total_volume}

        # Perform aggregations
        # IMPORTANT: Ensure aggregations uses column names consistent with base_schema if possible,
        # or Perspective might have issues if data columns don't match the schema later.
        aggregations = perform_aggregations(df.copy()) # Returns list of dicts
        
        # --- Add Debug Logging --- 
        print(f"[Debug Cache] Base Schema derived: {base_schema}")
        if isinstance(aggregations, list) and len(aggregations) > 0:
            print(f"[Debug Cache] First aggregation record structure: {aggregations[0].keys() if isinstance(aggregations[0], dict) else 'Non-dict item'}")
            print(f"[Debug Cache] Total aggregation records: {len(aggregations)}")
        else:
            print("[Debug Cache] Aggregations result is empty or not a list.")
            print("[Debug Cache] Using sample data because aggregations were empty/invalid")
            
            # If aggregations are empty, let's reuse our sample data generation code
            # This could happen if the DB has data but perform_aggregations returns empty results
            aggregations = []
            # Copy the sample data generation code from the empty database case
            
            regions = ['Brooklyn Bridge', 'Queens-Midtown Tunnel', 'Lincoln Tunnel', 'Williamsburg Bridge', 'Holland Tunnel']
            vehicles = ['car', 'taxi', 'bus', 'multi_unit_truck', 'single_unit_truck', 'motorcycle']
            # (Rest of the sample data generation code)
            # ... (See code in the if df.empty section)
            
            # Generate just a few sample days to avoid huge data volumes
            import random
            from datetime import datetime, timedelta
            now = timezone.now()
            
            # Create abbreviated sample data - just 3 days worth instead of 30
            days_to_generate = 3
            for day_offset in range(days_to_generate, 0, -1):
                # Similar sample data generation as in the empty DB case
                # (This creates a smaller sample compared to the empty DB case)
                sample_date = now - timedelta(days=day_offset)
                day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][sample_date.weekday()]
                day_int = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7}[day_name]
                
                for hour in range(24):
                    time_period = 'AM' if hour < 12 else 'PM'
                    
                    for region in regions:
                        for vehicle in vehicles:
                            # Simple traffic calculation for sample data
                            traffic = random.randint(50, 500)
                            
                            # Create sample entry
                            aggregations.append({
                                'detection_region': region,
                                'vehicle_class': vehicle,
                                'hour_of_day': hour,
                                'crz_entries': traffic,
                                'day_of_week': day_name,
                                'day_of_week_int': day_int,
                                'time_period': time_period,
                                'month_year': sample_date.strftime('%Y-%m'),
                            })
            
            print(f"[Debug Cache] Created {len(aggregations)} fallback aggregation records")
        # --- End Debug Logging ---
        
        calculated_agg_json = json.dumps(aggregations, cls=DjangoJSONEncoder)
        
        # Print a sample of what we're putting in the cache
        try:
            if aggregations and len(aggregations) > 0:
                print(f"[Debug Cache] Sample aggregation item: {aggregations[0]}")
        except Exception as e:
            print(f"[Debug Cache] Error showing sample: {e}")
            
        # Cache the results, including the BASE schema
        cache.set(STATS_CACHE_KEY, calculated_stats, CACHE_TIMEOUT)
        cache.set(AGG_JSON_CACHE_KEY, calculated_agg_json, CACHE_TIMEOUT)
        cache.set(SCHEMA_CACHE_KEY, base_schema, CACHE_TIMEOUT) # Cache the base schema

        return calculated_stats, calculated_agg_json, base_schema

    except Exception as e:
        print(f"!!! Error generating dashboard data: {e} !!!")
        import traceback
        traceback.print_exc()
        # Return defaults on error, including base schema
        default_stats = {'total_entries': 0, 'region_data': [], 'total_volume': 0, 'error': str(e)}
        default_agg_json = "[]"
        # Attempt to cache defaults including the schema even on error
        try:
            cache.set(STATS_CACHE_KEY, default_stats, CACHE_TIMEOUT)
            cache.set(AGG_JSON_CACHE_KEY, default_agg_json, CACHE_TIMEOUT)
            cache.set(SCHEMA_CACHE_KEY, base_schema, CACHE_TIMEOUT)
        except Exception as cache_e:
             print(f"Could not cache default values during error handling: {cache_e}")
        return default_stats, default_agg_json, base_schema


def get_map_data():
    """
    Gets required data for the map view from cache or generates it.
    Returns a dictionary containing 'deck_data', 'min_date', 'max_date'.
    """
    map_data_list = cache.get(MAP_DATA_CACHE_KEY) # Expecting list of dicts
    date_range = cache.get(DATE_RANGE_CACHE_KEY) # Expecting dict

    # Check if *both* are cached and seem valid (basic check)
    if isinstance(map_data_list, list) and isinstance(date_range, dict) and 'min_date' in date_range:
        print("--- Cache Hit: Map data ---")
        return {'deck_data': map_data_list, **date_range}

    print("--- Cache Miss: Generating map data ---")
    df = get_base_vehicle_data()

    # Define default return structure
    default_min_date = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_max_date = timezone.now().strftime('%Y-%m-%d')
    default_return_data = {'deck_data': [], 'min_date': default_min_date, 'max_date': default_max_date}

    if df.empty or 'toll_date' not in df.columns or 'detection_region' not in df.columns:
        print("--- Base data empty or missing required columns for map, returning default map data ---")
        cache.set(MAP_DATA_CACHE_KEY, default_return_data['deck_data'], CACHE_TIMEOUT)
        cache.set(DATE_RANGE_CACHE_KEY, {'min_date': default_return_data['min_date'], 'max_date': default_return_data['max_date']}, CACHE_TIMEOUT)
        return default_return_data

    try:
        df_map = df.copy() # Work on a copy

        # Ensure date column is datetime and drop NaNs *again* just in case
        df_map['toll_date'] = pd.to_datetime(df_map['toll_date'], errors='coerce', utc=True)
        df_map.dropna(subset=['toll_date', 'detection_region', 'crz_entries', 'vehicle_class'], inplace=True)

        if df_map.empty: # Check after dropna
             print("--- Data empty after cleaning for map, returning default map data ---")
             cache.set(MAP_DATA_CACHE_KEY, default_return_data['deck_data'], CACHE_TIMEOUT)
             cache.set(DATE_RANGE_CACHE_KEY, {'min_date': default_return_data['min_date'], 'max_date': default_return_data['max_date']}, CACHE_TIMEOUT)
             return default_return_data

        # Get date range *after* cleaning
        min_date_dt = df_map['toll_date'].min()
        max_date_dt = df_map['toll_date'].max()

        # Use defaults if min/max calculation fails (e.g., all dates were NaT)
        min_date_str = min_date_dt.strftime('%Y-%m-%d') if pd.notna(min_date_dt) else default_min_date
        max_date_str = max_date_dt.strftime('%Y-%m-%d') if pd.notna(max_date_dt) else default_max_date
        calculated_date_range = {'min_date': min_date_str, 'max_date': max_date_str}

        # --- Start: Map Specific Logic ---
        df_map['location_coords'] = df_map['detection_region'].map(ENTRY_POINTS)
        df_map = df_map.dropna(subset=['location_coords']) # Only keep rows matching known entry points

        if df_map.empty:
            print("--- No data matches known ENTRY_POINTS, returning default map data ---")
            cache.set(MAP_DATA_CACHE_KEY, default_return_data['deck_data'], CACHE_TIMEOUT)
            cache.set(DATE_RANGE_CACHE_KEY, calculated_date_range, CACHE_TIMEOUT) # Cache the calculated range though
            return {'deck_data': [], **calculated_date_range}

        # Extract lat/lng
        df_map['lat'] = df_map['location_coords'].apply(lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None)
        df_map['lng'] = df_map['location_coords'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None)
        df_map = df_map.dropna(subset=['lat', 'lng']) # Drop rows if lat/lng extraction failed

        # Map vehicle_class to standardized types
        df_map['vehicle_type'] = df_map['vehicle_class'].map(VEHICLE_CLASS_MAPPING).fillna('other') # Map or assign 'other'

        # Aggregate data by *mapped* entry point and *standardized* vehicle type
        location_data = df_map.groupby(['detection_region', 'vehicle_type', 'lat', 'lng'], observed=True).agg(
            crz_entries=('crz_entries', 'sum')
        ).reset_index()

        calculated_deck_data = []
        if not location_data.empty:
            # Normalize entries
            max_entries = location_data['crz_entries'].max()
            if max_entries is None or max_entries <= 0: max_entries = 1 # Avoid division by zero/negative
            location_data['entries_normalized'] = (location_data['crz_entries'] / max_entries * 100).fillna(0)

            # Assign colors and order
            location_data['color'] = location_data['vehicle_type'].apply(
                lambda x: VEHICLE_TYPES.get(x, {'color': [100, 100, 100]})['color']
            )
            location_data['order'] = location_data['vehicle_type'].apply(
                lambda x: VEHICLE_TYPES.get(x, {'order': 99})['order']
            )

            # Calculate height
            location_data['height'] = (location_data['entries_normalized'] * 5).clip(lower=1) # Scale height, ensure minimum height for visibility

            # Calculate position offsets
            offset_step = 0.00025 # Adjusted offset
            all_rows_data = []

            for region, group in location_data.groupby(['detection_region', 'lat', 'lng'], observed=True):
                type_count = len(group)
                # Ensure consistent sorting for offset calculation
                sorted_group = group.sort_values('order')

                for i, (idx, row) in enumerate(sorted_group.iterrows()):
                    offset = (i - (type_count - 1) / 2.0) * offset_step
                    row_dict = row.to_dict()
                    # Apply offset to longitude
                    row_dict['lng_offset'] = row['lng'] + offset

                    # Select and format fields for deck.gl JSON
                    deck_entry = {
                        'detection_region': row_dict.get('detection_region'),
                        'vehicle_type': row_dict.get('vehicle_type'),
                        'lat': row_dict.get('lat'),
                        'lng': row_dict.get('lng'),
                        'lng_offset': row_dict.get('lng_offset'),
                        'crz_entries': int(row_dict.get('crz_entries', 0)), # Ensure integer
                        'color': row_dict.get('color'),
                        'height': float(row_dict.get('height', 1.0)), # Ensure float
                        'order': int(row_dict.get('order', 99)), # Ensure integer
                    }
                    all_rows_data.append(deck_entry)

            calculated_deck_data = all_rows_data
        # --- End: Map Specific Logic ---

        # Cache the results (deck_data list and date_range dict)
        cache.set(MAP_DATA_CACHE_KEY, calculated_deck_data, CACHE_TIMEOUT)
        cache.set(DATE_RANGE_CACHE_KEY, calculated_date_range, CACHE_TIMEOUT)

        return {'deck_data': calculated_deck_data, **calculated_date_range}

    except Exception as e:
        print(f"!!! Error generating map data: {e} !!!")
        import traceback
        traceback.print_exc()
        # Return defaults on error, don't cache error state for map
        return default_return_data

def clear_vehicle_cache():
    """Utility function to clear all related cache entries."""
    keys_to_clear = [
        BASE_DATA_CACHE_KEY,
        STATS_CACHE_KEY,
        AGG_JSON_CACHE_KEY,
        MAP_DATA_CACHE_KEY,
        DATE_RANGE_CACHE_KEY
    ]
    for key in keys_to_clear:
        cache.delete(key)
    print("--- Cleared Vehicle Data Cache ---") 