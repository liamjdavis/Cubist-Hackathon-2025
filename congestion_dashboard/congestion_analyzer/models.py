from django.db import models

# Create your models here.

class VehicleEntry(models.Model):
    toll_date = models.DateField()
    toll_hour = models.PositiveSmallIntegerField()
    toll_10_minute_block = models.PositiveSmallIntegerField()
    minute_of_hour = models.PositiveSmallIntegerField()
    hour_of_day = models.PositiveSmallIntegerField()
    day_of_week_int = models.PositiveSmallIntegerField()
    day_of_week = models.CharField(max_length=10)
    toll_week = models.PositiveIntegerField()
    time_period = models.CharField(max_length=50)
    vehicle_class = models.CharField(max_length=50)
    detection_group = models.CharField(max_length=50)
    detection_region = models.CharField(max_length=50)
    crz_entries = models.PositiveIntegerField()
    excluded_roadway_entries = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.toll_date} {self.toll_hour}:{self.minute_of_hour} - {self.vehicle_class}"

    class Meta:
        verbose_name_plural = "Vehicle Entries"
