from django.shortcuts import render
import json

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

        # Step 2: Prepare context for the template
        # The data is already processed, we just need to pass it
        # along with constants the template JS might need (like VEHICLE_TYPES, ENTRY_POINTS)
        context = {
            # 'deck_gl_data': json.dumps(map_data_context.get('deck_data', []), cls=DjangoJSONEncoder), # Let template handle serialization if needed
            'min_date': map_data_context.get('min_date'),
            'max_date': map_data_context.get('max_date'),
            # Pass the constants needed by the JavaScript in the template
            'vehicle_types': json.dumps(VEHICLE_TYPES), # Ensure it's JSON for the template
            'entry_points': json.dumps(ENTRY_POINTS), # Ensure it's JSON for the template
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


# Original Panel/DeckGL code removed as it's handled by JS now