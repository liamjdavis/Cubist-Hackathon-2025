import pandas as pd
from django.utils import timezone
import json # Need json for the fallback

def prepare_context(total_entries, region_data, total_volume, aggregations):
    """Prepares the context dictionary for the template, focusing on the initial JSON payload."""
    print("[Context Builder] Preparing template context...")

    # Choose hourly aggregation as default for initial load
    agg_data = aggregations.get('hourly', pd.DataFrame())
    agg_json = "[]" # Default empty JSON

    if not agg_data.empty:
        print(f"[Context Builder] Using hourly aggregation ({len(agg_data)} records) for initial JSON payload.")
        try:
            # Attempt JSON conversion
            agg_json = agg_data.to_json(orient='records', date_format='iso')
            print(f"[Context Builder] Successfully converted hourly aggregation to JSON.")
            # Safely print sample record (optional)
            # print("[Context Builder] Sample pre-aggregated record:")
            # print(agg_data.iloc[0].to_dict())
        except Exception as e:
            print(f"[Context Builder] Error converting aggregated data to JSON: {e}. Falling back to empty JSON.")
            agg_json = "[]" # Ensure fallback on error
    else:
        # This covers cases where hourly aggregation failed or resulted in an empty DataFrame
        print("[Context Builder] Hourly aggregation data is empty. Sending empty JSON dataset to Perspective.")

    context = {
        'total_entries': total_entries,
        'total_volume': total_volume,
        'region_data': region_data,
        'agg_json': agg_json,  # Initially sending hourly aggregation JSON
        'current_time': timezone.now(),
        'live_metrics_enabled': True, # Keep this for now
        # Other aggregations (daily, monthly) are available in the `aggregations` dict 
        # but not passed directly to the template initially.
        # They could be exposed via an API endpoint if needed for dynamic loading.
    }
    print("[Context Builder] Context preparation complete.")
    return context 