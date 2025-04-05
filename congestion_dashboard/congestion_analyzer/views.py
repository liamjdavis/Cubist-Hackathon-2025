from django.shortcuts import render
from django.utils import timezone
import json # Added for potential use, though context builder might handle it

# Import the caching utility function
from .cache_utils import get_dashboard_data, clear_vehicle_cache

# Remove old helper imports if they are no longer directly used here
# from .view_helpers.data_fetcher import get_vehicle_data
# from .view_helpers.stats_calculator import calculate_base_stats
# from .view_helpers.aggregator import perform_aggregations

# Keep context builder if it's still used for formatting, otherwise remove
# from .view_helpers.context_builder import prepare_context # Check if needed

def index(request):
    """
    View function for the main visualization dashboard.
    Uses the caching utility to get processed data and schema.
    """
    print("--- Starting index view processing (using cache) ---")
    
    # Check if we need to force refresh - you can add a URL parameter for controlling this if needed
    force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
    if force_refresh:
        print("--- Forcing cache refresh as requested ---")
        clear_vehicle_cache()
        
    # For testing/development when the DB is empty, you might want to
    # always clear the cache to ensure sample data is regenerated each time
    # During normal operation, comment this out to benefit from caching
    # clear_vehicle_cache() # Comment this out for production
    
    try:
        # Step 1: Get data and schema from cache or generate if missed
        stats_data, agg_json_string, schema_data = get_dashboard_data()

        # Step 2: Prepare context for the template
        context = {
            'total_entries': stats_data.get('total_entries', 0),
            'region_data': stats_data.get('region_data', []),
            'total_volume': stats_data.get('total_volume', 0),
            'agg_json': agg_json_string, # Already a JSON string
            'perspective_schema': json.dumps(schema_data), # Pass schema as JSON
            'current_time': timezone.now(), # Keep adding dynamic elements
            'live_metrics_enabled': True, # Or based on settings
            'error_message': stats_data.get('error') # Pass error if present
        }

        # Step 3: Render template
        response = render(request, 'congestion_analyzer/index.html', context)
        print("--- Index view processing complete (using cache) ---")
        return response

    except Exception as e:
        # Basic error handling for the view itself (e.g., template rendering errors)
        print(f"!!! FATAL ERROR in index view rendering: {e} !!!")
        import traceback
        traceback.print_exc()

        # Return a minimal context or render an error page
        context = {
            'total_entries': 0, 'total_volume': 0, 'region_data': [],
            'agg_json': "[]",
            'perspective_schema': "{}", # Empty schema JSON
            'current_time': timezone.now(),
            'live_metrics_enabled': False,
            'error_message': f'An unexpected error occurred during page load: {e}'
        }
        # Consider rendering a specific error template:
        # return render(request, 'congestion_analyzer/error.html', context, status=500)
        return render(request, 'congestion_analyzer/index.html', context) # Return main page with error state