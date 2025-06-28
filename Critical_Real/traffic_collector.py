import os
import time as time_module  # Renamed to avoid conflict
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv
from traffic_config import MONITOR_POINTS, COLLECTION_INTERVAL, API_TIMEOUT, MAX_RETRIES, RoutePoint

load_dotenv()

class TrafficDataCollector:
    def __init__(self, db_path: str = "traffic_data.db"):
        self.api_key = os.getenv('TOMTOM_API_KEY')
        self.db_path = db_path
        self._init_db()
        self._verify_api_key()
        
    def _verify_api_key(self):
        """Verify that the API key is valid"""
        if not self.api_key:
            print("❌ TOMTOM_API_KEY is not set in .env file")
            return False
            
        test_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        params = {
            'point': '12.9716,77.5946',  # MG Road
            'unit': 'KMPH',
            'key': self.api_key,
            'zoom': 12
        }
        
        try:
            response = requests.get(test_url, params=params, timeout=10)
            if response.status_code == 200:
                print("✅ API key is valid and working")
                return True
            elif response.status_code == 403:
                print("❌ Invalid API key. Please check your TOMTOM_API_KEY")
            else:
                print(f"❌ API error (HTTP {response.status_code}): {response.text[:200]}")
        except Exception as e:
            print(f"❌ Failed to connect to TomTom API: {str(e)}")
        
        return False
        
    def _init_db(self):
        """Initialize SQLite database for storing traffic data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS traffic_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    point_name TEXT,
                    latitude REAL,
                    longitude REAL,
                    timestamp DATETIME,
                    current_speed REAL,
                    free_flow_speed REAL,
                    traffic_incidents INTEGER
                )
            ''')
            conn.commit()
    
    def get_traffic_data(self, point: 'RoutePoint') -> Dict[str, Any]:
        """Get traffic data for a specific point with retry logic"""
        # Using Traffic Flow API v4 (most stable version) with direct URL construction
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={point.lat},{point.lon}&unit=KMPH&key={self.api_key}"
        
        if not self.api_key:
            print("❌ API key is not set. Please set TOMTOM_API_KEY in .env file")
            return None
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=API_TIMEOUT)
                print(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Get incident count if we have valid data
                    traffic_incidents = self._get_incident_count(point.lat, point.lon) if data.get('flowSegmentData') else 0
                    
                    return {
                        'point_name': point.name,
                        'latitude': point.lat,
                        'longitude': point.lon,
                        'timestamp': datetime.utcnow().isoformat(),
                        'current_speed': data.get('flowSegmentData', {}).get('currentSpeed'),
                        'free_flow_speed': data.get('flowSegmentData', {}).get('freeFlowSpeed'),
                        'traffic_incidents': traffic_incidents
                    }
                else:
                    print(f"Error status code: {response.status_code}")
                    print(f"Response content: {response.text[:200]}...")
                    last_error = Exception(f"HTTP {response.status_code}: {response.text[:100]}")
                    if attempt < MAX_RETRIES - 1:
                        time_module.sleep(1 * (attempt + 1))
                        continue
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:  # Don't sleep on the last attempt
                    time_module.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            except Exception as e:
                last_error = e
                break
        
        print(f"❌ Failed to get traffic data for {point.name} after {MAX_RETRIES} attempts")
        if last_error:
            print(f"   Error: {str(last_error)}")
        return None
    
    def _get_incident_count(self, lat: float, lon: float, radius_km: int = 2) -> int:
        """Get number of traffic incidents in the area with retry logic"""
        # Using Traffic Incidents API v4 (most stable version) with direct URL construction
        bbox = self._calculate_bounding_box(lat, lon, radius_km)
        url = f"https://api.tomtom.com/traffic/services/4/incidentDetails/s3/{bbox}/10/-1/json?key={self.api_key}&language=en-GB"
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=API_TIMEOUT)
                print(f"Incident API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    return len(data.get('incidents', []))
                else:
                    print(f"Incident API error: {response.status_code}")
                    print(f"Content: {response.text[:100]}...")
                    last_error = Exception(f"HTTP {response.status_code}: {response.text[:100]}")
                    if attempt < MAX_RETRIES - 1:
                        time_module.sleep(1 * (attempt + 1))
                        continue
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:  # Don't sleep on the last attempt
                    time_module.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            except Exception as e:
                last_error = e
                break
        
        print(f"⚠️  Failed to get incident data after {MAX_RETRIES} attempts")
        if last_error:
            print(f"   Error: {str(last_error)}")
        return 0  # Return 0 incidents if we can't get the data
    
    def _calculate_bounding_box(self, lat: float, lon: float, radius_km: int) -> str:
        """Calculate bounding box coordinates for incident search"""
        # Approximate conversion: 1 degree ~ 111 km
        lat_delta = radius_km / 111
        lon_delta = radius_km / (111 * abs(lat) / 90)
        
        min_lat = lat - lat_delta
        max_lat = lat + lat_delta
        min_lon = lon - lon_delta
        max_lon = lon + lon_delta
        
        return f"{min_lon},{min_lat},{max_lon},{max_lat}"
    
    def save_traffic_data(self, data: Dict[str, Any]):
        """Save traffic data to database"""
        if not data:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO traffic_data 
                (point_name, latitude, longitude, timestamp, current_speed, free_flow_speed, traffic_incidents)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['point_name'],
                data['latitude'],
                data['longitude'],
                data['timestamp'],
                data['current_speed'],
                data['free_flow_speed'],
                data['traffic_incidents']
            ))
            conn.commit()
    
    def collect_data(self):
        """Collect traffic data for all points"""
        start_time = datetime.now()
        print(f"\n🔄 Starting data collection at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        successful_points = 0
        total_points = len(MONITOR_POINTS)
        
        for point in MONITOR_POINTS:
            try:
                print(f"\n📍 Processing {point.name}...")
                traffic_data = self.get_traffic_data(point)
                if traffic_data:
                    self.save_traffic_data(traffic_data)
                    print(f"✅ Saved data for {point.name}")
                    successful_points += 1
                else:
                    print(f"⚠️  No data received for {point.name}")
                
                # Small delay between API calls
                time_module.sleep(1)
                
            except Exception as e:
                print(f"❌ Error processing {point.name}: {str(e)}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n📊 Collection Complete!")
        print(f"   • Successful points: {successful_points}/{total_points}")
        print(f"   • Duration: {duration:.2f} seconds")
        print(f"   • Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    collector = TrafficDataCollector()
    collector.collect_data()

if __name__ == "__main__":
    main()