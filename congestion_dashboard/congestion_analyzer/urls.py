from django.urls import path
from . import views
from . import map_views

app_name = 'congestion_analyzer'

urlpatterns = [
    path('', views.index, name='index'),
    path('map/', map_views.map, name='map'),
    path('anomalies/', views.anomalies, name='anomalies'),
    path('get_anomalies/', views.get_anomalies, name='get_anomalies'),
    path('get_anomaly_history/', views.get_anomaly_history, name='get_anomaly_history'),
]