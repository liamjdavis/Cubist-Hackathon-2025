from django.shortcuts import render
import json
from shapely import Polygon, Point
import random
import math

# Import the caching utility function and constants
from .cache_utils import get_map_data, VEHICLE_TYPES, ENTRY_POINTS

# Remove unused imports:
# from .models import VehicleEntry
# from django.db.models import Sum
# from django.utils import timezone
# import pandas as pd
# import pprint
# from django.core.serializers.json import DjangoJSONEncoder
# import panel as pn
# from datetime import datetime, timedelta

# pn.extension('deckgl') # No longer creating DeckGL object in Python
def generate_random_points_in_polygon(poly, num_points, min_lon, min_lat, max_lon, max_lat):
    points = []
    while len(points) < num_points:
        # Generate a random point within the bounding box
        random_lon = random.uniform(min_lon, max_lon)
        random_lat = random.uniform(min_lat, max_lat)
        p = Point(random_lon, random_lat)
        # Only add the point if it lies within the polygon
        if poly.contains(p):
            # Here we return the coordinates in (latitude, longitude) order if desired
            points.append((random_lat, random_lon))
    return points

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth using the haversine formula.
    Returns the distance in kilometers.
    """
    R = 6371  # Earth's radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

def get_random_points(vertices, num_points):
    polygon_coords = [(lon, lat) for lat, lon in vertices]
    polygon = Polygon(polygon_coords)
        
    min_lon, min_lat, max_lon, max_lat = polygon.bounds
    
    random_points = generate_random_points_in_polygon(polygon, num_points, min_lon, min_lat, max_lon, max_lat)
    random_points_dict = []
    for i, (lat, lon) in enumerate(random_points, start=1):
        distances = {}
        for name, (ep_lat, ep_lon) in ENTRY_POINTS.items():
            distance = haversine(lat, lon, ep_lat, ep_lon)
            distances[name] = distance
        random_points_dict.append({'lat': lat, 'lon': lon, 'score' : 0, 'previous_score' : 0, 'distances' : distances})
        
    return random_points_dict
    

    

def map(request):
    """
    View function for the map visualization.
    Uses the caching utility to get pre-processed map data.
    Passes data to the template for JavaScript-based Deck.gl rendering.
    """
    print("--- Starting map view processing (using cache) ---")
    try:
        # Step 1: Get map data from cache or generate if missed
        map_data_context = get_map_data()
        
        vertices = [
        (40.75888, -73.95778),
        (40.77349, -73.99493),
        (40.76962, -73.99524),
        (40.76312, -74.00047),
        (40.75519, -74.00734),
        (40.75018, -74.00931),
        (40.74765, -74.00854),
        (40.74134, -74.00949),
        (40.73926, -74.01069),
        (40.7229, -74.01202),
        (40.70459, -74.01747),
        (40.70107, -74.01644),
        (40.70029, -74.01146),
        (40.70704, -73.99896),
        (40.71064, -73.97876),
        (40.72898, -73.97052),
        (40.73613, -73.97367),
        (40.74386, -73.97079)
        ]

        # Convert the list into the format Shapely expects: (longitude, latitude)
       
        dict_points = get_random_points(vertices, num_points=20)

        # Generate 15 random points within the polygon
        

        # Step 2: Prepare context for the template
        # The data is already processed, we just need to pass it
        # along with constants the template JS might need (like VEHICLE_TYPES, ENTRY_POINTS)
        context = {
            # 'deck_gl_data': json.dumps(map_data_context.get('deck_data', []), cls=DjangoJSONEncoder), # Let template handle serialization if needed
            'min_date': map_data_context.get('min_date'),
            'max_date': map_data_context.get('max_date'),
            # Pass the constants needed by the JavaScript in the template
            'vehicle_types': json.dumps(VEHICLE_TYPES), # Ensure it's JSON for the template
            'entry_points': json.dumps(ENTRY_POINTS), 
            'points_data': json.dumps(dict_points), # Ensure it's JSON for the template
            # The map template's JS expects raw data for vehicleTypes and entryPoints,
            # and the data for the layer will be fetched via JS simulation or API later.
            # We don't pass the deck_data directly here as the template is set up for JS fetching.
            'error_message': map_data_context.get('error') # Pass error if present
        }

        # --- Note on map.html structure ---
        # The current map.html uses simulated data fetched via JavaScript (`fetchData` function).
        # It doesn't directly use the `deck_data` passed from the Python view for the main layer.
        # It *does* use `vehicle_types` and `entry_points` passed from Python.
        # If we wanted the Python view to provide the *initial* data for the map layer,
        # we would need to: 
        # 1. Pass `map_data_context.get('deck_data', [])` to the template context.
        # 2. Modify the `initializeMap` function in `map.html` to use this passed data
        #    instead of calling `fetchData` for the initial load.
        # 3. Serialize the `deck_data` appropriately (e.g., json.dumps).
        # For now, we'll stick to the existing JS structure and only pass the necessary constants.

        # Step 3: Render template
        response = render(request, 'congestion_analyzer/map.html', context)
        print("--- Map view processing complete (using cache) ---")
        return response

    except Exception as e:
        # Basic error handling for the view itself
        print(f"!!! FATAL ERROR in map view rendering: {e} !!!")
        import traceback
        traceback.print_exc()

        # Return minimal context or error page
        context = {
            'min_date': None, 'max_date': None,
            'vehicle_types': json.dumps(VEHICLE_TYPES), # Still provide defaults if possible
            'entry_points': json.dumps(ENTRY_POINTS),
            'error_message': f'An unexpected error occurred during map page load: {e}'
        }
        return render(request, 'congestion_analyzer/map.html', context)
