import json
import asyncio
import time
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from .congestion_scoring import congestion_score_instance, update_scores, TollData
import random

def get_scores(request):
    """
    Django view for getting the current congestion scores
    """
    # Use asyncio to run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    scores = loop.run_until_complete(update_scores())
    loop.close()
    
    return JsonResponse(scores)

def stream_scores(request):
    """
    Django view that streams SSE (Server-Sent Events) with congestion scores
    """
    def event_stream():
        while True:
            # Use a new event loop for each iteration
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                scores = loop.run_until_complete(update_scores())
                # Format as SSE
                yield f"data: {json.dumps(scores)}\n\n"
            except Exception as e:
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
            finally:
                loop.close()
            
            # Sleep between updates
            time.sleep(30)
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable buffering for Nginx
    return response

def get_heatmap_points(request):
    """
    Return current congestion scores formatted for the heatmap
    """
    # Get cached scores instead of recomputing
    scores = congestion_score_instance.scores

    # Get vertices from the map_views module
    from .map_views import get_random_points

    # Use the same congestion zone polygon from map_views
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
    
    # Get fixed points (only generate them once)
    if not hasattr(get_heatmap_points, "points_cache"):
        get_heatmap_points.points_cache = get_random_points(vertices, num_points=50)  # Increased from 15 to 50

    # Update the fixed points with real congestion scores
    for point in get_heatmap_points.points_cache:
        # Store previous score
        point['previous_score'] = point.get('score', 0)
        
        # Calculate score based on distance-weighted average of real entry point scores
        total_weight = 0
        weighted_score = 0
        
        for entry_name, distance in point['distances'].items():
            # Closer entry points have higher weights (inverse distance)
            weight = 1.0 / (1.0 + distance)
            total_weight += weight
            
            # Get score for this entry point if available
            entry_score = scores.get(entry_name, 50)  # Default to 50 if no data
            weighted_score += entry_score * weight
        
        # Calculate final weighted score
        if total_weight > 0:
            point['score'] = min(100, max(1, weighted_score / total_weight))
        else:
            point['score'] = 50  # Fallback
    
    return JsonResponse(get_heatmap_points.points_cache, safe=False)