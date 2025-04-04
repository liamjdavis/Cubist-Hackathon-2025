from django.shortcuts import render
from .models import VehicleEntry
from django.db.models import Sum, Count, Avg
from django.utils import timezone
import pandas as pd
import json
import pprint

def index(request):
    """
    View function for the main visualization dashboard.
    Uses pandas to process data from the VehicleEntry model for visualization.
    """
    # Get filter parameters from request
    vehicle_filter = request.GET.get('vehicle_class', None)
    start_date = request.GET.get('start_date', None)
    end_date = request.GET.get('end_date', None)
    
    # Query all entries with filters
    queryset = VehicleEntry.objects.all()
    
    # Apply Django ORM filters
    if vehicle_filter:
        queryset = queryset.filter(vehicle_class=vehicle_filter)
    if start_date:
        queryset = queryset.filter(toll_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(toll_date__lte=end_date)
    
    # Convert to DataFrame for processing
    entries_data = pd.DataFrame(list(queryset.values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries'
    )))
    
    # Get total entries
    total_entries = len(entries_data) if not entries_data.empty else 0
    
    # Process data with pandas instead of perspective
    if not entries_data.empty:
        # Get entries by vehicle class
        vehicle_class_data = entries_data.groupby('vehicle_class')['crz_entries'].sum().reset_index()
        vehicle_class_data = vehicle_class_data.rename(columns={'crz_entries': 'count'})
        vehicle_class_data = vehicle_class_data.sort_values('count', ascending=False)
        vehicle_class_data = vehicle_class_data.to_dict('records')
        
        # Get entries by day of week
        day_of_week_data = entries_data.groupby(['day_of_week', 'day_of_week_int'])['crz_entries'].sum().reset_index()
        day_of_week_data = day_of_week_data.rename(columns={'crz_entries': 'count'})
        day_of_week_data = day_of_week_data.sort_values('day_of_week_int')
        day_of_week_data = day_of_week_data.to_dict('records')
        
        # Get entries by hour of day
        hour_data = entries_data.groupby('hour_of_day')['crz_entries'].sum().reset_index()
        hour_data = hour_data.rename(columns={'crz_entries': 'count'})
        hour_data = hour_data.sort_values('hour_of_day')
        hour_data = hour_data.to_dict('records')
        
        # Get entries by region
        region_data = entries_data.groupby('detection_region')['crz_entries'].sum().reset_index()
        region_data = region_data.rename(columns={'crz_entries': 'count'})
        region_data = region_data.sort_values('count', ascending=False)
        region_data = region_data.to_dict('records')
        
        # NEW: Add region time analysis - traffic by hour for each region
        region_hour_data = entries_data.groupby(['detection_region', 'hour_of_day'])['crz_entries'].sum().reset_index()
        region_hour_pivot = region_hour_data.pivot(index='hour_of_day', columns='detection_region', values='crz_entries')
        region_hour_pivot = region_hour_pivot.fillna(0)
        
        # Convert the pivot table to a format suitable for Chart.js
        region_hours_labels = region_hour_pivot.index.tolist()
        region_names = region_hour_pivot.columns.tolist()
        region_hour_series = []
        
        # Create a dataset for each region
        for region in region_names:
            region_hour_series.append({
                'region': region,
                'data': region_hour_pivot[region].tolist()
            })
        
        # NEW: Entry point comparison data
        entry_point_data = {
            'labels': [item['detection_region'] for item in region_data],
            'counts': [item['count'] for item in region_data]
        }
        
        # Get unique vehicle classes for filter dropdown
        vehicle_classes = entries_data['vehicle_class'].unique().tolist()
    else:
        # Handle empty data case
        vehicle_class_data = []
        day_of_week_data = []
        hour_data = []
        region_data = []
        vehicle_classes = []
        region_hour_series = []
        region_hours_labels = []
        entry_point_data = {'labels': [], 'counts': []}
    
    # Current time for the dashboard refresh indicator
    current_time = timezone.now()
    
    # Calculate total traffic volume
    total_volume = sum(item['count'] for item in region_data) if region_data else 0
    
    context = {
        'total_entries': total_entries,
        'total_volume': total_volume,
        'vehicle_class_data': vehicle_class_data,
        'day_of_week_data': day_of_week_data,
        'hour_data': hour_data,
        'region_data': region_data,
        'region_hour_series': json.dumps(region_hour_series),
        'region_hours_labels': json.dumps(region_hours_labels),
        'entry_point_data': json.dumps(entry_point_data),
        'current_time': current_time,
        'vehicle_classes': vehicle_classes,
        'selected_vehicle': vehicle_filter,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'congestion_analyzer/index.html', context)