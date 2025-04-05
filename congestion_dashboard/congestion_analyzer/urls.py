from django.urls import path
from . import views
from . import map_views

app_name = 'congestion_analyzer'

urlpatterns = [
    path('', views.index, name='index'),
    path('map/', map_views.map, name='map'),
    path('anomalies/', views.anomalies, name='anomalies'),
]