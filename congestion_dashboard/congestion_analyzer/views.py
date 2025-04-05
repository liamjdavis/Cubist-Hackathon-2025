from django.shortcuts import render
from django.utils import timezone

# Import helper functions from the new modules
from .view_helpers.data_fetcher import get_vehicle_data
from .view_helpers.stats_calculator import calculate_base_stats
from .view_helpers.aggregator import perform_aggregations
from .view_helpers.context_builder import prepare_context

def index(request):
    """
    View function for the main visualization dashboard.
    Orchestrates data fetching, processing, and rendering using helper modules.
    """
    print("--- Starting index view processing ---")
    try:
        # Step 1: Get data using data_fetcher
        df = get_vehicle_data()
        # Use df.copy() when passing to subsequent functions if they modify it,
        # although current helpers aim not to modify the input DataFrame in place.
        # However, copying provides safety against potential future modifications.

        # Step 2: Calculate base statistics using stats_calculator
        total_entries, region_data, total_volume = calculate_base_stats(df.copy())

        # Step 3: Perform aggregations using aggregator
        aggregations = perform_aggregations(df.copy()) 

        # Step 4: Prepare context for the template using context_builder
        context = prepare_context(total_entries, region_data, total_volume, aggregations)

        # Step 5: Render template
        response = render(request, 'congestion_analyzer/index.html', context)
        print("--- Index view processing complete ---")
        return response

    except Exception as e:
        # Basic error handling for the view
        print(f"!!! FATAL ERROR in index view orchestration: {e} !!!")
        # Log the full traceback for debugging
        import traceback
        traceback.print_exc()
        
        # Return a minimal context or render an error page
        context = {
            'total_entries': 0, 'total_volume': 0, 'region_data': [],
            'agg_json': "[]", 'current_time': timezone.now(),
            'live_metrics_enabled': False, 
            'error_message': f'An unexpected error occurred: {e}' # Provide a generic message
        }
        # Consider rendering a specific error template:
        # return render(request, 'congestion_analyzer/error.html', context, status=500)
        return render(request, 'congestion_analyzer/index.html', context) # Return main page with error state