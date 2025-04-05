from datetime import datetime
import math
from typing import Dict, List
import httpx
import asyncio
from pydantic import BaseModel

# Vehicle class weights (normalized between 0-1)
VEHICLE_WEIGHTS = {
    "1 - Cars, Pickups and Vans": 0.4,
    "2 - Single-Unit Trucks": 0.7,
    "3 - Multi-Unit Trucks": 1.0,  # Highest impact
    "4 - Buses": 0.8,
    "5 - Motorcycles": 0.2,  # Lowest impact
    "TLC Taxi/FHV": 0.5
}

# Time period weights (normalized between 0-1)
TIME_PERIOD_WEIGHTS = {
    "Overnight": 0.3,
    "Off-Peak": 0.6,
    "Peak": 1.0
}

# Time decay parameters
DECAY_FACTOR = 0.05  # Reduced from 0.1 for slower decay
LEVY_SCALE = 2.0     # Scale parameter for Lévy distribution
MIN_DECAY = 0.9      # Minimum decay factor to prevent too rapid decay

def levy_decay(time_diff: float) -> float:
    """
    Calculate decay factor using Lévy distribution properties.
    Returns a value between MIN_DECAY and 1.0
    """
    if time_diff <= 0:
        return 1.0
        
    # Use a modified Lévy-like decay function
    decay = 1.0 / (1.0 + math.sqrt(DECAY_FACTOR * time_diff))
    
    # Ensure decay doesn't go below minimum
    return max(MIN_DECAY, decay)

class TollData(BaseModel):
    toll_date: str
    toll_hour: str
    toll_10_minute_block: str
    minute_of_hour: str
    hour_of_day: str
    day_of_week_int: str
    day_of_week: str
    toll_week: str
    time_period: str
    vehicle_class: str
    detection_group: str
    detection_region: str
    crz_entries: str
    excluded_roadway_entries: str

    class Config:
        extra = "allow"  # Allow extra fields in the JSON

class CongestionScore:
    def __init__(self):
        self.scores: Dict[str, float] = {}
        self.last_update: Dict[str, datetime] = {}
        self.historical_max: Dict[str, float] = {}
        self.historical_min: Dict[str, float] = {}
        self.base_max: Dict[str, float] = {}  # Store typical max values for each location
        self.score_history: Dict[str, List[float]] = {}  # Track recent scores
        self.history_window = 10  # Number of recent scores to keep

    def calculate_score(self, data: TollData) -> float:
        # Base score from vehicle count and excluded entries
        base_score = int(data.crz_entries)
        excluded_entries = int(data.excluded_roadway_entries) if data.excluded_roadway_entries else 0
        total_traffic = base_score + excluded_entries
        
        # Get weights
        vehicle_weight = VEHICLE_WEIGHTS.get(data.vehicle_class, 0.5)
        time_period_weight = TIME_PERIOD_WEIGHTS.get(data.time_period, 0.5)
        
        # Time-based adjustments
        hour = int(data.hour_of_day)
        time_factor = 1.0
        
        # Rush hour adjustment (7-10 AM and 4-7 PM)
        if (7 <= hour <= 10) or (16 <= hour <= 19):
            time_factor = 1.2
        
        # Late night reduction (11 PM - 5 AM)
        elif (23 <= hour <= 24) or (0 <= hour <= 5):
            time_factor = 0.6
        
        # Weekend adjustment
        if data.day_of_week.lower() in ['saturday', 'sunday']:
            time_factor *= 0.8
        
        # Reduce taxi weight after 9 PM
        if data.vehicle_class == "TLC Taxi/FHV" and hour >= 21:
            time_factor *= 0.3
        
        # Calculate raw score
        raw_score = (
            total_traffic * 
            vehicle_weight * 
            time_period_weight * 
            time_factor
        )
        
        # Update historical min/max for this location
        if data.detection_group not in self.historical_max:
            self.historical_max[data.detection_group] = raw_score
            self.historical_min[data.detection_group] = raw_score
            self.base_max[data.detection_group] = raw_score * 1.5  # Set initial expected maximum
            self.score_history[data.detection_group] = []
        else:
            # Update historical values with heavy dampening
            if raw_score > self.historical_max[data.detection_group]:
                self.historical_max[data.detection_group] = (
                    0.95 * self.historical_max[data.detection_group] + 0.05 * raw_score
                )
            if raw_score < self.historical_min[data.detection_group]:
                self.historical_min[data.detection_group] = (
                    0.95 * self.historical_min[data.detection_group] + 0.05 * raw_score
                )
            
            # Update base_max very slowly
            if raw_score > self.base_max[data.detection_group]:
                self.base_max[data.detection_group] = (
                    0.98 * self.base_max[data.detection_group] + 0.02 * raw_score
                )
        
        # Normalize score between 1-100 using adaptive scaling
        min_val = self.historical_min[data.detection_group]
        max_val = self.base_max[data.detection_group]
        
        if max_val == min_val:
            normalized_score = 50.0  # Default to middle if no range
        else:
            # Scale to 1-100 with dampening for extreme values
            raw_normalized = 1 + 99 * (raw_score - min_val) / (max_val - min_val)
            if raw_normalized > 100:
                # Dampen values above 100 using log scaling
                excess = raw_normalized - 100
                normalized_score = 100 + math.log(1 + excess)
            else:
                normalized_score = raw_normalized
            
            # Ensure final score is between 1 and 100
            normalized_score = max(1, min(100, normalized_score))
        
        # Update score history
        history = self.score_history.get(data.detection_group, [])
        history.append(normalized_score)
        self.score_history[data.detection_group] = history[-self.history_window:]
        
        # Return smoothed score (average of recent scores)
        return sum(self.score_history[data.detection_group]) / len(self.score_history[data.detection_group])

    def update_score(self, detection_group: str, score: float):
        current_time = datetime.now()
        
        # Apply time decay to existing score
        if detection_group in self.scores:
            time_diff = (current_time - self.last_update[detection_group]).total_seconds() / 3600
            decay_factor = levy_decay(time_diff)
            
            # Calculate new score with heavy smoothing
            old_score = self.scores[detection_group]
            decayed_score = old_score * decay_factor
            
            # Weighted average heavily favoring the existing score
            self.scores[detection_group] = max(1, min(100, 0.8 * decayed_score + 0.2 * score))
        else:
            self.scores[detection_group] = score
            
        self.last_update[detection_group] = current_time


# Create a global instance to be used throughout the app
congestion_score_instance = CongestionScore()

async def fetch_toll_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://data.ny.gov/resource/t6yz-b64h.json")
        return response.json()

async def update_scores():
    """Update all congestion scores with fresh data"""
    try:
        data = await fetch_toll_data()
        for entry in data:
            toll_data = TollData(**entry)
            score = congestion_score_instance.calculate_score(toll_data)
            congestion_score_instance.update_score(toll_data.detection_group, score)
        return congestion_score_instance.scores
    except Exception as e:
        print(f"Error updating scores: {e}")
        return congestion_score_instance.scores