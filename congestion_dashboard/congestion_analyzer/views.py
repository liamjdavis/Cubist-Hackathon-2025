from django.shortcuts import render
from .models import VehicleEntry
from django.db.models import Sum
from django.utils import timezone
import pandas as pd
import json
import pprint
from django.core.serializers.json import DjangoJSONEncoder

def index(request):
    """
    View function for the main visualization dashboard.
    Creates a pipeline from database to pre-aggregated DataFrame to Perspective.
    """
    # Step 1: Query the database
    queryset = VehicleEntry.objects.all().values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
        'detection_group', 'toll_week'
    )
    
    # Step 2: Convert directly to DataFrame
    df = pd.DataFrame(list(queryset))
    
    # Get total entries count for stats
    total_entries = len(df) if not df.empty else 0
    
    if not df.empty:
        # Ensure date column is correctly formatted
        if 'toll_date' in df.columns:
            # Convert to datetime for proper aggregation
            df['toll_date'] = pd.to_datetime(df['toll_date'])
            # Extract month and year for aggregation
            df['month_year'] = df['toll_date'].dt.strftime('%Y-%m')
            # Keep the original datetime format
        
        # Create region summary for stats display
        region_summary = df.groupby('detection_region')['crz_entries'].sum().reset_index()
        region_summary = region_summary.rename(columns={'crz_entries': 'count'})
        region_summary = region_summary.sort_values('count', ascending=False)
        region_data = region_summary.to_dict('records')
        
        # Calculate total volume
        total_volume = df['crz_entries'].sum()
        
        # Step 3: Pre-aggregate data at different levels
        print(f"Original DataFrame size: {len(df)} records")
        
        # Level 1: Hourly aggregation (most compact)
        hourly_agg = df.groupby([
            'detection_region',
            'vehicle_class',
            'hour_of_day'
        ])['crz_entries'].sum().reset_index()
        print(f"Hourly aggregation: {len(hourly_agg)} records")
        
        # Level 2: Daily aggregation
        daily_agg = df.groupby([
            'detection_region',
            'vehicle_class',
            'day_of_week',
            'day_of_week_int'
        ])['crz_entries'].sum().reset_index()
        print(f"Daily aggregation: {len(daily_agg)} records")
        
        # Level 3: Monthly aggregation
        monthly_agg = df.groupby([
            'detection_region',
            'vehicle_class',
            'month_year'
        ])['crz_entries'].sum().reset_index()
        print(f"Monthly aggregation: {len(monthly_agg)} records")
        
        # Step 4: Convert to JSON for Perspective
        # Create a single aggregated dataset in optimal form for Perspective
        # - Include all needed dimensions for slicing
        # - Pre-aggregate to reduce data transfer size
        
        # Choose hourly aggregation as default (most compact yet informative)
        agg_data = hourly_agg
        
        # Convert to JSON
        agg_json = agg_data.to_json(orient='records', date_format='iso')
        print(f"Sending {len(agg_data)} pre-aggregated records to Perspective")
        
        # Also provide sample information
        print("Sample pre-aggregated record:")
        if len(agg_data) > 0:
            print(agg_data.iloc[0].to_dict())
    else:
        # Handle empty data case
        agg_json = "[]"
        region_data = []
        total_volume = 0
    
    # Current time for the dashboard refresh indicator
    current_time = timezone.now()

    context = {
        'total_entries': total_entries,
        'total_volume': total_volume,
        'region_data': region_data,
        'agg_json': agg_json,  # Pre-aggregated data
        'current_time': current_time,
    }
    
    return render(request, 'congestion_analyzer/index.html', context)