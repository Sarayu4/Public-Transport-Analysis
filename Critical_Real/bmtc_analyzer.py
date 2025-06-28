import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import folium
from folium.plugins import HeatMap
from typing import List, Dict, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta
import os

class BMTCAnalyzer:
    def __init__(self, data_path: str = "Public-Transport-Analysis/data_2025.geojson"):
        self.data_path = data_path
        self.bmtc_data = None
        self.bus_stops = None
        self.processed = False
        
    def load_data(self) -> bool:
        """Load and preprocess BMTC data"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if data is a GeoJSON feature collection
            if 'features' in data:
                features = data['features']
                
                # Create a list of valid features (points with coordinates)
                valid_features = []
                for feature in features:
                    if feature.get('geometry', {}).get('type') == 'Point':
                        valid_features.append(feature)
                
                if not valid_features:
                    print("No valid point features found in the GeoJSON")
                    return False
                
                # Create GeoDataFrame from features
                self.bmtc_data = gpd.GeoDataFrame.from_features(valid_features)
                
                # Add required columns if they don't exist
                if 'name' not in self.bmtc_data.columns:
                    self.bmtc_data['name'] = 'Bus Stop ' + (self.bmtc_data.index + 1).astype(str)
                    
            else:
                # Handle case where data is a direct array of features
                if isinstance(data, list):
                    self.bmtc_data = gpd.GeoDataFrame(data)
                else:
                    print("Unsupported data format. Expected GeoJSON FeatureCollection or array of features.")
                    return False
            
            # Process bus stops
            self.bus_stops = self._process_bus_stops()
            self.processed = True
            return True
            
        except Exception as e:
            print(f"Error loading BMTC data: {str(e)}")
            return False
    
    def _process_bus_stops(self) -> gpd.GeoDataFrame:
        """Process and clean bus stop data"""
        if self.bmtc_data is None or self.bmtc_data.empty:
            return gpd.GeoDataFrame()
            
        try:
            # Ensure we have a geometry column
            if 'geometry' not in self.bmtc_data.columns:
                # Try to create geometry from lat/lon if they exist
                if all(col in self.bmtc_data.columns for col in ['latitude', 'longitude']):
                    self.bmtc_data['geometry'] = self.bmtc_data.apply(
                        lambda row: Point(row['longitude'], row['latitude']), 
                        axis=1
                    )
                else:
                    print("No geometry data found in BMTC data")
                    return gpd.GeoDataFrame()
            
            # Create a copy with only necessary columns
            columns = ['name', 'geometry']
            if 'id' in self.bmtc_data.columns:
                columns.append('id')
            if 'highway' in self.bmtc_data.columns:
                columns.append('highway')
                
            # Create a clean GeoDataFrame
            bus_stops = gpd.GeoDataFrame(
                self.bmtc_data[columns],
                geometry='geometry',
                crs="EPSG:4326"  # WGS84
            )
            
            # Add latitude and longitude columns if they don't exist
            if 'latitude' not in bus_stops.columns or 'longitude' not in bus_stops.columns:
                bus_stops['longitude'] = bus_stops['geometry'].x
                bus_stops['latitude'] = bus_stops['geometry'].y
                
            return bus_stops
            
        except Exception as e:
            print(f"Error processing bus stops: {str(e)}")
            return gpd.GeoDataFrame()
            
        # Create a clean DataFrame with relevant columns
        stops = self.bmtc_data.copy()
        
        # Ensure we have required columns
        if 'name' not in stops.columns:
            stops['name'] = stops.get('loc_name', stops.get('alt_name', 'Unnamed Stop'))
            
        # Clean up the data
        stops = stops[['name', 'geometry', '@id', 'highway', 'public_transport']]
        stops = stops.dropna(subset=['name', 'geometry'])
        
        # Add coordinates as separate columns
        stops['longitude'] = stops.geometry.x
        stops['latitude'] = stops.geometry.y
        
        return stops
    
    def get_nearby_stops(self, point: Tuple[float, float], radius_km: float = 0.5) -> gpd.GeoDataFrame:
        """Find bus stops within a radius of a point (lat, lng)"""
        if self.bus_stops is None or self.bus_stops.empty:
            return gpd.GeoDataFrame()
            
        # Create a point and buffer
        center = Point(point[1], point[0])  # Note: GeoPandas uses (x,y) = (lng,lat)
        buffer = center.buffer(radius_km / 111.32)  # Approx 1 degree = 111.32 km
        
        # Find stops within buffer
        nearby = self.bus_stops[self.bus_stops.geometry.within(buffer)]
        return nearby
    
    def create_bus_stop_map(self, center: Tuple[float, float] = (12.9716, 77.5946), 
                           zoom: int = 12) -> folium.Map:
        """Create a folium map with bus stops"""
        if self.bus_stops is None or self.bus_stops.empty:
            return None
            
        # Create map centered on Bangalore
        m = folium.Map(location=center, zoom_start=zoom, tiles='OpenStreetMap')
        
        # Add bus stops to the map
        for idx, stop in self.bus_stops.iterrows():
            folium.CircleMarker(
                location=[stop.geometry.y, stop.geometry.x],
                radius=3,
                color='blue',
                fill=True,
                fill_color='blue',
                fill_opacity=0.7,
                popup=f"<b>{stop.get('name', 'Unnamed')}</b><br>ID: {stop.get('@id', 'N/A')}"
            ).add_to(m)
        
        return m
    
    def correlate_with_traffic(self, traffic_data: pd.DataFrame) -> pd.DataFrame:
        """
        Correlate bus stops with traffic data
        
        Args:
            traffic_data: DataFrame with columns ['timestamp', 'latitude', 'longitude', 'traffic_index']
            
        Returns:
            DataFrame with traffic impact on bus stops
        """
        if self.bus_stops is None or self.bus_stops.empty:
            return pd.DataFrame()
            
        # Convert traffic data to GeoDataFrame
        traffic_gdf = gpd.GeoDataFrame(
            traffic_data,
            geometry=gpd.points_from_xy(traffic_data.longitude, traffic_data.latitude)
        )
        
        # Spatial join to find traffic near bus stops
        result = gpd.sjoin(
            self.bus_stops,
            traffic_gdf,
            how='left',
            predicate='intersects'
        )
        
        # Aggregate traffic metrics by bus stop
        if not result.empty:
            agg_result = result.groupby(['name', 'geometry']).agg({
                'traffic_index': ['mean', 'max', 'count']
            }).reset_index()
            
            # Flatten column names
            agg_result.columns = ['_'.join(col).strip('_') for col in agg_result.columns.values]
            agg_result = agg_result.rename(columns={
                'name_': 'name',
                'geometry_': 'geometry',
                'traffic_index_mean': 'avg_traffic',
                'traffic_index_max': 'max_traffic',
                'traffic_index_count': 'data_points'
            })
            
            return agg_result
        return pd.DataFrame()
