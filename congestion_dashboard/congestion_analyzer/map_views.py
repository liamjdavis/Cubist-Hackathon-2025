from django.shortcuts import render
from .models import VehicleEntry
from django.db.models import Sum
from django.utils import timezone
import pandas as pd
import json
import pprint
from django.core.serializers.json import DjangoJSONEncoder
import panel as pn
from datetime import datetime, timedelta

pn.extension('deckgl')

def map(request):
    ENTRY_POINTS = {
        'Queensboro Bridge': [40.7561, -73.9525],
        'Queens-Midtown Tunnel': [40.7527, -73.9675],
        'Williamsburg Bridge': [40.7127, -73.9707],
        'Manhattan Bridge': [40.7074, -73.9891],
        'Brooklyn Bridge': [40.7061, -73.9969],
        'Hugh Carey Tunnel': [40.7007, -74.0178],
        'Holland Tunnel': [40.7282, -74.0287],
        'Lincoln Tunnel': [40.7614, -73.9536],
        'FDR Drive at 60th Street': [40.7614, -73.9536],
        'East 60th Street': [40.7614, -73.9536],
        'West 60th Street': [40.7714, -73.9836]
    }
    
    # Define vehicle types and their corresponding colors
    VEHICLE_TYPES = {
        'car': {'name': 'Passenger Cars', 'color': [65, 182, 196], 'order': 0},
        'taxi': {'name': 'Taxis', 'color': [254, 221, 0], 'order': 1},
        'bus': {'name': 'Buses', 'color': [44, 127, 184], 'order': 2}, 
        'multi_unit_truck': {'name': 'Multi-Unit Trucks', 'color': [127, 60, 141], 'order': 3},
        'single_unit_truck': {'name': 'Single Unit Trucks', 'color': [217, 95, 2], 'order': 4},
        'motorcycle': {'name': 'Motorcycles', 'color': [231, 41, 138], 'order': 5}
    }

    queryset = VehicleEntry.objects.all().values(
        'toll_date', 'hour_of_day', 'day_of_week', 'day_of_week_int',
        'vehicle_class', 'detection_region', 'crz_entries', 'time_period',
        'detection_group', 'toll_week'
    )
    
    df = pd.DataFrame(list(queryset))
    
    if not df.empty:
        # Ensure date column is correctly formatted
        if 'toll_date' in df.columns:
            # Convert to datetime for proper aggregation
            df['toll_date'] = pd.to_datetime(df['toll_date'])
            # Extract month and year for aggregation
            df['month_year'] = df['toll_date'].dt.strftime('%Y-%m')
            
            # Map entry points to coordinates
            df['location_coords'] = df['detection_region'].map(ENTRY_POINTS)
        
            # Drop rows with missing coordinates
            df = df.dropna(subset=['detection_region', 'crz_entries'])
            df = df[df['detection_region'].str.strip() != '']
            
            # Extract lat and lng from coordinates
            df['lat'] = df['location_coords'].apply(lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None)
            df['lng'] = df['location_coords'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None)
            
            # Drop rows with invalid coordinates
            df = df.dropna(subset=['lat', 'lng'])
            
            # Map vehicle_class to standardized categories if needed
            vehicle_class_mapping = {
                'Passenger Car': 'car',
                'Taxi': 'taxi',
                'Bus': 'bus',
                'Multi-Unit Truck': 'multi_unit_truck',
                'Single-Unit Truck': 'single_unit_truck',
                'Motorcycle': 'motorcycle'
                # Add other mappings as needed
            }
            
            # Apply the mapping if the data needs standardization
            if 'vehicle_class' in df.columns:
                df['vehicle_type'] = df['vehicle_class'].map(vehicle_class_mapping)
                # If mapping fails, keep original value
                df['vehicle_type'] = df['vehicle_type'].fillna(df['vehicle_class'])
            
            # Aggregate data by location and vehicle type
            location_data = df.groupby(['detection_region', 'vehicle_type', 'lat', 'lng']).agg({
                'crz_entries': 'sum'  # Sum up all entries for each entry point and vehicle type
            }).reset_index()
            
            # Calculate max entries for normalization
            max_entries = location_data['crz_entries'].max()
            
            # Prepare data for deck.gl with vehicle type information
            location_data['entries_normalized'] = location_data['crz_entries'] / max_entries * 100
            
            # Assign colors and order based on vehicle type
            location_data['color'] = location_data['vehicle_type'].apply(
                lambda x: VEHICLE_TYPES.get(x, {'color': [100, 100, 100]})['color']
            )
            
            location_data['order'] = location_data['vehicle_type'].apply(
                lambda x: VEHICLE_TYPES.get(x, {'order': 99})['order']
            )
            
            # Calculate height based on entry count for 3D visualization
            location_data['height'] = location_data['entries_normalized'] * 50  # Scale height
            
            # Calculate position offsets for side-by-side display
            # First group by detection region to get all vehicle types at each entry point
            region_groups = location_data.groupby('detection_region')
            
            # Process each entry point to calculate offsets
            for region, group in region_groups:
                # How many vehicle types at this entry point
                type_count = len(group)
                # Calculate offset for each vehicle type (in coordinates)
                offset_step = 0.0003  # Small coordinate offset
                
                # Sort by order to ensure consistent positioning
                sorted_indices = group.sort_values('order').index
                
                # Apply offsets
                for i, idx in enumerate(sorted_indices):
                    # Center the group around the original position
                    offset = (i - (type_count - 1) / 2) * offset_step
                    # Apply offset to longitude (east-west direction)
                    location_data.at[idx, 'lng_offset'] = location_data.at[idx, 'lng'] + offset
            
            # Convert to dictionaries for JavaScript
            deck_data = location_data.to_dict(orient='records')
            
            # Get date range for the widget
            min_date = df['toll_date'].dropna().min()
            max_date = df['toll_date'].dropna().max()
            
            # Set default dates if no valid dates are found
            if pd.isna(min_date) or pd.isna(max_date):
                min_date = datetime(2025, 1, 28)  # Start at Jan 28
                max_date = datetime(2025, 3, 28)  # End at March 28
            else:
                # Convert to datetime if they're not already
                min_date = pd.to_datetime(min_date)
                max_date = pd.to_datetime(max_date)
            
            # Format dates as strings
            min_date = min_date.strftime('%Y-%m-%d')
            max_date = max_date.strftime('%Y-%m-%d')
        else:
            # Handle case where toll_date is missing
            return None
    else:
        # Handle empty data case
        return None
    
    MAPBOX_KEY = ""

    if MAPBOX_KEY:
        map_style = "mapbox://styles/mapbox/dark-v9"
    else:
        map_style = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
    
    json_spec = {
        "initialViewState": {
            "bearing": 12,
            "latitude": 40.736839,
            "longitude": -73.989723,
            "maxZoom": 20,
            "minZoom": 5,
            "pitch": 50,
            "zoom": 11
        },
        "layers": [
            {
                "@@type": "ColumnLayer",
                "id": "vehicle-type-layer",
                "data": deck_data,
                "pickable": True,
                "extruded": True,
                "diskResolution": 12,
                "radius": 80,  # Slightly smaller to accommodate multiple columns
                "getPosition": "@@=[lng_offset || lng, lat]", # Use offset longitude if available
                "getFillColor": "@@=color",
                "getElevation": "@@=height",
                "elevationScale": 1,
                "visible": True
            }
        ],
        "mapStyle": map_style,
        "views": [
            {"@@type": "MapView", "controller": True}
        ]
    }

    deck_gl = pn.pane.DeckGL(json_spec, mapbox_api_key=MAPBOX_KEY, sizing_mode='stretch_width', height=600)
    
    # Pass additional context data
    context = {
        'deck_gl': deck_gl,
        'min_date': min_date,
        'max_date': max_date,
        'vehicle_types': json.dumps(VEHICLE_TYPES),
        'entry_points': json.dumps(ENTRY_POINTS)
    }
    
    return render(request, 'congestion_analyzer/map.html', context)