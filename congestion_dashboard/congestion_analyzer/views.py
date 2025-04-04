from django.shortcuts import render
from .models import VehicleEntry
from django.db.models import Sum, Count
from django.utils import timezone

# Create your views here.
def index(request):
    """
    View function for the main visualization dashboard.
    Prepares data from the VehicleEntry model for visualization.
    """
    # Get some basic statistics
    total_entries = VehicleEntry.objects.count()
    
    # Get entries by vehicle class
    vehicle_class_data = VehicleEntry.objects.values('vehicle_class').annotate(
        count=Sum('crz_entries')
    ).order_by('-count')
    
    # Get entries by day of week
    day_of_week_data = VehicleEntry.objects.values('day_of_week').annotate(
        count=Sum('crz_entries')
    ).order_by('day_of_week_int')
    
    # Get entries by hour of day
    hour_data = VehicleEntry.objects.values('hour_of_day').annotate(
        count=Sum('crz_entries')
    ).order_by('hour_of_day')
    
    # Get entries by region
    region_data = VehicleEntry.objects.values('detection_region').annotate(
        count=Sum('crz_entries')
    ).order_by('-count')
    
    # Current time for the dashboard refresh indicator
    current_time = timezone.now()
    
    context = {
        'total_entries': total_entries,
        'vehicle_class_data': vehicle_class_data,
        'day_of_week_data': day_of_week_data,
        'hour_data': hour_data,
        'region_data': region_data,
        'current_time': current_time,
    }
    
    return render(request, 'congestion_analyzer/index.html', context)