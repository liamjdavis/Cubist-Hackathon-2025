from datetime import datetime, timedelta
from django.utils import timezone
from ddsketch import LogCollapsingLowestDenseDDSketch
from .models import VehicleEntry
import numpy as np

class AnomalyDetector:
    def __init__(self, relative_accuracy=0.01):
        self.relative_accuracy = relative_accuracy
        self.sketch = LogCollapsingLowestDenseDDSketch(relative_accuracy=self.relative_accuracy)
        self.historical_data = []
        self.thresholds = {
            'p99': 0.99,
            'p95': 0.95,
            'p90': 0.90
        }
        self.anomaly_history = []  # Store historical anomalies
        self.vehicle_sketches = {}  # Sketches for each vehicle type - ONLY KEEPING THIS ONE

    def update(self, entry):
        """Update the sketch with new entry data"""
        if entry.crz_entries > 0:  # Only process non-zero entries
            # Update main sketch (for reference only)
            self.sketch.add(entry.crz_entries)
            
            # Update vehicle-specific sketch
            if entry.vehicle_class not in self.vehicle_sketches:
                self.vehicle_sketches[entry.vehicle_class] = LogCollapsingLowestDenseDDSketch(relative_accuracy=self.relative_accuracy)
            self.vehicle_sketches[entry.vehicle_class].add(entry.crz_entries)
            
            # Store historical data point
            self.historical_data.append({
                'timestamp': entry.toll_date,
                'hour': entry.toll_hour,
                'minute': entry.minute_of_hour,
                'entries': entry.crz_entries,
                'vehicle_class': entry.vehicle_class,
                'detection_region': entry.detection_region,
                'time_period': entry.time_period
            })

    def detect_anomalies(self, sample_size=1000, recent_bias=0.5):
        """
        Detect anomalies using different thresholds for all data dimensions
        with optimized sampling for large datasets.
        
        Args:
            sample_size: Maximum number of entries to analyze per vehicle type
            recent_bias: Fraction of samples to take from most recent data (0-1)
        """
        if not self.historical_data or not self.vehicle_sketches:
            return []
            
        # Clear previous anomalies when doing a fresh detection
        self.anomaly_history = []
        anomalies = []
        
        # Get list of vehicle types once
        vehicle_types = list(self.vehicle_sketches.keys())
        print(f"Processing anomalies for {len(vehicle_types)} vehicle types")
        
        # Pre-calculate expected values for each vehicle type and threshold to avoid redundant calculations
        vehicle_thresholds = {}
        for vehicle_class in vehicle_types:
            sketch = self.vehicle_sketches[vehicle_class]
            vehicle_thresholds[vehicle_class] = {
                # Upper bounds (for spikes)
                'p99_upper': sketch.get_quantile_value(0.99),
                'p95_upper': sketch.get_quantile_value(0.95),
                'p90_upper': sketch.get_quantile_value(0.90),
                # Lower bounds (for drops)
                'p99_lower': sketch.get_quantile_value(0.01),  # 1 - 0.99
                'p95_lower': sketch.get_quantile_value(0.05),  # 1 - 0.95
                'p90_lower': sketch.get_quantile_value(0.10),  # 1 - 0.90
                # Median for reference
                'median': sketch.get_quantile_value(0.5)
            }
        
        # Count entries processed for progress tracking
        total_processed = 0
        
        # Process entries by vehicle type with smart sampling
        for vehicle_class in vehicle_types:
            # Find all entries for this vehicle type
            vehicle_entries = [entry for entry in self.historical_data if entry['vehicle_class'] == vehicle_class]
            total_entries = len(vehicle_entries)
            
            if total_entries == 0:
                continue
                
            print(f"Sampling from {total_entries} entries for vehicle type {vehicle_class}")
            
            # Smart sampling strategy:
            # 1. Get recent entries (prioritize anomalies in recent data)
            # 2. Get random sample from older entries
            # 3. Combine them within sample_size limit
            
            # Sort by timestamp (recent first)
            vehicle_entries.sort(key=lambda x: (x['timestamp'], x['hour'], x['minute']), reverse=True)
            
            # Calculate how many recent vs random samples to take
            recent_count = min(int(sample_size * recent_bias), total_entries)
            random_count = min(sample_size - recent_count, total_entries - recent_count)
            
            # Take recent entries
            recent_entries = vehicle_entries[:recent_count]
            
            # Take random sample from remaining entries
            remaining_entries = vehicle_entries[recent_count:]
            random_entries = []
            if remaining_entries and random_count > 0:
                # Use numpy for efficient random sampling without replacement
                if len(remaining_entries) > random_count:
                    indices = np.random.choice(len(remaining_entries), random_count, replace=False)
                    random_entries = [remaining_entries[i] for i in indices]
                else:
                    random_entries = remaining_entries  # Take all if fewer than requested
            
            # Combine samples
            sampled_entries = recent_entries + random_entries
            print(f"Analyzing {len(sampled_entries)} samples ({recent_count} recent, {len(random_entries)} random)")
            
            # Get pre-calculated thresholds for this vehicle type
            thresholds = vehicle_thresholds[vehicle_class]
            
            # Process the sampled entries efficiently
            for i, entry in enumerate(sampled_entries):
                current_value = entry['entries']
                
                # Check for spikes - ONLY add the highest threshold that applies
                if current_value > thresholds['p99_upper']:
                    self._add_anomaly(entry, current_value, thresholds['p99_upper'], 'p99', 'spike', anomalies)
                elif current_value > thresholds['p95_upper']:
                    self._add_anomaly(entry, current_value, thresholds['p95_upper'], 'p95', 'spike', anomalies)
                elif current_value > thresholds['p90_upper']:
                    self._add_anomaly(entry, current_value, thresholds['p90_upper'], 'p90', 'spike', anomalies)
                
                # Check for drops - ONLY add the lowest threshold that applies
                if current_value < thresholds['p99_lower']:
                    self._add_anomaly(entry, current_value, thresholds['p99_lower'], 'p99', 'drop', anomalies)
                elif current_value < thresholds['p95_lower']:
                    self._add_anomaly(entry, current_value, thresholds['p95_lower'], 'p95', 'drop', anomalies)
                elif current_value < thresholds['p90_lower']:
                    self._add_anomaly(entry, current_value, thresholds['p90_lower'], 'p90', 'drop', anomalies)
                
                # Increment counter and show progress every 1000 entries
                total_processed += 1
                if total_processed % 1000 == 0:
                    print(f"Progress: Processed {total_processed} entries so far")
        
        print(f"Detected {len(self.anomaly_history)} anomalies")
        return self.anomaly_history
    
    def _add_anomaly(self, entry_data, current_value, threshold_value, threshold_name, anomaly_type, anomalies):
        """Helper method to create and add anomaly records (extracted from _check_thresholds)"""
        # Calculate deviation
        if anomaly_type == 'spike':
            deviation = ((current_value - threshold_value) / threshold_value) * 100 if threshold_value > 0 else 100
        else:  # drop
            deviation = ((current_value - threshold_value) / threshold_value) * 100 if threshold_value > 0 else -100
        
        # Create anomaly record
        anomaly = {
            'timestamp': entry_data['timestamp'],
            'hour': entry_data['hour'],
            'minute': entry_data['minute'],
            'type': anomaly_type,
            'threshold': threshold_name,
            'entries': current_value,
            'expected': threshold_value,
            'deviation': deviation,
            'vehicle_class': entry_data['vehicle_class'],
            'detection_region': entry_data['detection_region'],
            'time_period': entry_data.get('time_period', ''),
            'context': 'vehicle'
        }
        
        # Add to current batch
        anomalies.append(anomaly)
        
        # Add to history if not a duplicate
        if not any(self._is_duplicate(a, anomaly) for a in self.anomaly_history):
            self.anomaly_history.append(anomaly)
                
    def _check_thresholds(self, current_data, current_value, expected_value, sketch, context, anomalies):
        """Helper method to check thresholds and record anomalies"""
        # Check for spikes (above expected)
        for threshold_name, threshold in self.thresholds.items():
            # Calculate threshold-specific expected value instead of using median for all
            threshold_expected = sketch.get_quantile_value(threshold)
            upper_bound = threshold_expected
            
            if current_value > upper_bound:
                deviation = ((current_value - threshold_expected) / threshold_expected) * 100 if threshold_expected > 0 else 100
                anomaly = {
                    'timestamp': current_data['timestamp'],
                    'hour': current_data['hour'],
                    'minute': current_data['minute'],
                    'type': 'spike',
                    'threshold': threshold_name,
                    'entries': current_value,
                    'expected': threshold_expected,  # Use threshold-specific expected value
                    'deviation': deviation,
                    'vehicle_class': current_data['vehicle_class'],
                    'detection_region': current_data['detection_region'],
                    'time_period': current_data['time_period'],
                    'context': context
                }
                anomalies.append(anomaly)
                # Avoid duplicate records in history
                if not any(self._is_duplicate(a, anomaly) for a in self.anomaly_history):
                    self.anomaly_history.append(anomaly)
        
        # Check for drops (below expected)
        for threshold_name, threshold in self.thresholds.items():
            # Calculate threshold-specific expected value for drops
            inverse_threshold = 1 - threshold
            threshold_expected = sketch.get_quantile_value(inverse_threshold)
            lower_bound = threshold_expected
            
            if current_value < lower_bound:
                deviation = ((current_value - threshold_expected) / threshold_expected) * 100 if threshold_expected > 0 else -100
                anomaly = {
                    'timestamp': current_data['timestamp'],
                    'hour': current_data['hour'],
                    'minute': current_data['minute'],
                    'type': 'drop',
                    'threshold': threshold_name,
                    'entries': current_value,
                    'expected': threshold_expected,  # Use threshold-specific expected value
                    'deviation': deviation,
                    'vehicle_class': current_data['vehicle_class'],
                    'detection_region': current_data['detection_region'],
                    'time_period': current_data['time_period'],
                    'context': context
                }
                anomalies.append(anomaly)
                # Avoid duplicate records in history
                if not any(self._is_duplicate(a, anomaly) for a in self.anomaly_history):
                    self.anomaly_history.append(anomaly)
    
    def _is_duplicate(self, a1, a2):
        """Check if two anomalies are likely duplicates"""
        return (a1['timestamp'] == a2['timestamp'] and 
                a1['hour'] == a2['hour'] and 
                a1['minute'] == a2['minute'] and
                a1['type'] == a2['type'] and
                a1['threshold'] == a2['threshold'] and
                a1['vehicle_class'] == a2['vehicle_class'] and
                a1['detection_region'] == a2['detection_region'])

    def get_anomaly_history(self):
        """Return the historical anomalies"""
        return self.anomaly_history