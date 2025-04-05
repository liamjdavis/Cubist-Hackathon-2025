from django.shortcuts import render
from django.utils import timezone
import json # Added for potential use, though context builder might handle it
from django.http import JsonResponse

# Import the caching utility function
from .cache_utils import get_dashboard_data, clear_vehicle_cache, clear_anomaly_cache, get_cached_anomalies
from .anomaly_detection import AnomalyDetector
from .models import VehicleEntry
from datetime import datetime, timedelta, date

anomaly_detector = AnomalyDetector()

# Remove old helper imports if they are no longer directly used here
# from .view_helpers.data_fetcher import get_vehicle_data
# from .view_helpers.stats_calculator import calculate_base_stats
# from .view_helpers.aggregator import perform_aggregations

# Keep context builder if it's still used for formatting, otherwise remove
# from .view_helpers.context_builder import prepare_context # Check if needed
# Custom JSON encoder to handle date objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

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

def anomalies(request):
    """View function for the anomaly detection page."""
    try:
        print("Starting anomaly detection with cache...")
        
        # Check if we need to force refresh
        force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
        if force_refresh:
            print("--- Forcing anomaly cache refresh as requested ---")
            clear_anomaly_cache()
        
        # Get data from cache or generate it
        anomalies_json, first_date, last_date, total_entries = get_cached_anomalies()
        
        if total_entries == 0:
            print("No entries found in database")
            context = {
                'anomalies': '[]',
                'current_time': timezone.now(),
                'total_entries': 0,
                'date_range': 'No data available',
                'error_message': 'No entries found in the database'
            }
            return render(request, 'congestion_analyzer/anomalies.html', context)
        
        # Prepare context with cached data
        context = {
            'anomalies': anomalies_json,  # Already a JSON string from cache
            'current_time': timezone.now(),
            'total_entries': total_entries,
            'date_range': f"{first_date} to {last_date}"
        }
        
        print("Rendering anomalies page with cached data...")
        return render(request, 'congestion_analyzer/anomalies.html', context)
        
    except Exception as e:
        print(f"Error in anomalies view: {str(e)}")
        import traceback
        traceback.print_exc()
        
        context = {
            'anomalies': '[]',
            'current_time': timezone.now(),
            'total_entries': 0,
            'date_range': 'Error loading data',
            'error_message': f'Error loading anomalies: {str(e)}'
        }
        return render(request, 'congestion_analyzer/anomalies.html', context)
    
def get_anomalies(request):
    """API endpoint to get current anomalies from the last 10 minutes"""
    try:
        # Get the current time for filtering
        current_time = timezone.now()
        print(f"Current time: {current_time}")
        
        # Get the most recent entries for detection
        latest_entries = VehicleEntry.objects.order_by('-toll_date', '-toll_hour', '-minute_of_hour')[:100]
        
        if latest_entries.exists():
            print(f"Found {latest_entries.count()} recent entries for live anomaly detection")
            for entry in latest_entries:
                anomaly_detector.update(entry)
        
        # Detect all anomalies
        all_anomalies = anomaly_detector.detect_anomalies()
        
        # Calculate the cutoff time (10 minutes ago)
        cutoff_time = current_time - timedelta(minutes=10)
        print(f"Filtering anomalies after: {cutoff_time}")
        
        # Filter anomalies to only include the most recent ones
        if all_anomalies:
            # Sort anomalies by timestamp (most recent first) - handle different types safely
            for anomaly in all_anomalies:
                # Convert timestamp to string if it's not already
                if not isinstance(anomaly['timestamp'], str):
                    anomaly['timestamp'] = str(anomaly['timestamp'])
                
                # Extract date components safely
                try:
                    anomaly['date_obj'] = datetime.fromisoformat(anomaly['timestamp'])
                except (ValueError, TypeError):
                    # Fallback for date parsing errors - use current time as default
                    anomaly['date_obj'] = datetime.now()
                
                # Create full datetime
                anomaly['full_datetime'] = datetime.combine(
                    anomaly['date_obj'].date(),
                    datetime.min.time()
                ) + timedelta(hours=int(anomaly['hour']), minutes=int(anomaly['minute']))
            
            # Sort by the full datetime (most recent first)
            all_anomalies.sort(key=lambda x: x['full_datetime'], reverse=True)
            
            # Take only the most recent 5 anomalies
            recent_anomalies = all_anomalies[:5]
            
            # Clean up the temporary fields we added
            for anomaly in recent_anomalies:
                del anomaly['date_obj']
                del anomaly['full_datetime']
        else:
            recent_anomalies = []
        
        print(f"API: Detected {len(all_anomalies)} total anomalies, returning {len(recent_anomalies)} most recent")
        return JsonResponse({'anomalies': recent_anomalies}, encoder=CustomJSONEncoder)
    except Exception as e:
        print(f"Error in get_anomalies: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'anomalies': []})
                
def get_anomaly_history(request):
    """API endpoint to get historical anomalies"""
    try:
        history = anomaly_detector.get_anomaly_history()
        return JsonResponse({'anomalies': history}, encoder=CustomJSONEncoder)
    except Exception as e:
        print(f"Error in get_anomaly_history: {str(e)}")  # Debug print
        return JsonResponse({'anomalies': []})