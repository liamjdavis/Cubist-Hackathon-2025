import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from congestion_analyzer.models import VehicleEntry

class Command(BaseCommand):
    help = 'Import vehicle entries from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        # Counter for tracking progress
        counter = 0
        
        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            
            # Create a list to store all VehicleEntry instances
            vehicle_entries = []
            
            for row in reader:
                try:
                    # Parse the date from Toll Date
                    toll_date = datetime.strptime(row['Toll Date'], '%m/%d/%Y').date()
                    
                    # Extract hour from the Toll Hour string
                    toll_hour_str = row['Toll Hour']
                    toll_hour_dt = datetime.strptime(toll_hour_str, '%m/%d/%Y %I:%M:%S %p')
                    toll_hour = toll_hour_dt.hour
                    
                    # Extract which 10-minute block it is from the Toll 10 Minute Block
                    block_str = row['Toll 10 Minute Block']
                    block_dt = datetime.strptime(block_str, '%m/%d/%Y %I:%M:%S %p')
                    # Calculate the 10-minute block (0-5)
                    toll_10_minute_block = block_dt.minute // 10
                    
                    # Parse minute of hour
                    minute_of_hour = int(row['Minute of Hour'])
                    
                    # Parse toll week (first day of the week)
                    toll_week_str = row['Toll Week']
                    toll_week_dt = datetime.strptime(toll_week_str, '%m/%d/%Y').date()
                    # Store week number of year
                    toll_week = toll_week_dt.isocalendar()[1]
                    
                    # Create VehicleEntry instance
                    entry = VehicleEntry(
                        toll_date=toll_date,
                        toll_hour=toll_hour,
                        toll_10_minute_block=toll_10_minute_block,
                        minute_of_hour=minute_of_hour,
                        hour_of_day=int(row['Hour of Day']),
                        day_of_week_int=int(row['Day of Week Int']),
                        day_of_week=row['Day of Week'],
                        toll_week=toll_week,
                        time_period=row['Time Period'],
                        vehicle_class=row['Vehicle Class'],
                        detection_group=row['Detection Group'],
                        detection_region=row['Detection Region'],
                        crz_entries=int(row['CRZ Entries']),
                        excluded_roadway_entries=int(row['Excluded Roadway Entries'])
                    )
                    
                    vehicle_entries.append(entry)
                    counter += 1
                    
                    # Bulk create in batches of 1000 to avoid memory issues
                    if counter % 1000 == 0:
                        VehicleEntry.objects.bulk_create(vehicle_entries)
                        vehicle_entries = []
                        self.stdout.write(f"Imported {counter} entries...")
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on row {counter+1}: {str(e)}"))
                    # Display the problematic row for debugging
                    self.stdout.write(self.style.ERROR(f"Row data: {row}"))
            
            # Create any remaining entries
            if vehicle_entries:
                VehicleEntry.objects.bulk_create(vehicle_entries)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {counter} vehicle entries'))