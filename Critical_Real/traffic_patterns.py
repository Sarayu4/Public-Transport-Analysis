"""
Traffic Pattern Analysis Module
Analyzes historical traffic data to identify patterns and trends
"""
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import calendar
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import plotly.express as px
import plotly.graph_objects as go

class TrafficPatternAnalyzer:
    """Analyzes historical traffic data to extract meaningful patterns"""
    
    def __init__(self, db_path="traffic_data.db"):
        """Initialize the pattern analyzer"""
        self.db_path = db_path
        
    def get_hourly_patterns(self, days_back=30, location=None):
        """
        Analyze hourly traffic patterns over the specified period
        
        Args:
            days_back: Number of days to look back
            location: Optional location filter
            
        Returns:
            DataFrame with hourly traffic averages
        """
        # Get historical data
        df = self._get_historical_data(days_back, location)
        
        if df.empty:
            return pd.DataFrame()
        
        # Convert timestamp to datetime and extract hour
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        
        # Calculate traffic index
        df['traffic_index'] = df.apply(
            lambda row: max(0, min(100, int(100 * (1 - row['current_speed'] / row['free_flow_speed']))))
            if row['free_flow_speed'] > 0 and row['current_speed'] > 0 else 0, 
            axis=1
        )
        
        # Group by hour and calculate average metrics
        hourly_patterns = df.groupby('hour').agg({
            'traffic_index': 'mean',
            'current_speed': 'mean',
            'free_flow_speed': 'mean',
            'traffic_incidents': 'mean'
        }).reset_index()
        
        return hourly_patterns
    
    def get_daily_patterns(self, days_back=90, location=None):
        """
        Analyze daily traffic patterns over the specified period
        
        Args:
            days_back: Number of days to look back
            location: Optional location filter
            
        Returns:
            DataFrame with daily traffic averages
        """
        # Get historical data
        df = self._get_historical_data(days_back, location)
        
        if df.empty:
            return pd.DataFrame()
            
        # Convert timestamp to datetime and extract day
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['day'] = df['timestamp'].dt.day_name()
        
        # Calculate traffic index
        df['traffic_index'] = df.apply(
            lambda row: max(0, min(100, int(100 * (1 - row['current_speed'] / row['free_flow_speed']))))
            if row['free_flow_speed'] > 0 and row['current_speed'] > 0 else 0, 
            axis=1
        )
        
        # Define day order for sorting
        day_order = {day: i for i, day in enumerate(calendar.day_name)}
        
        # Group by day and calculate average metrics
        daily_patterns = df.groupby('day').agg({
            'traffic_index': 'mean',
            'current_speed': 'mean',
            'free_flow_speed': 'mean',
            'traffic_incidents': 'mean'
        }).reset_index()
        
        # Sort by day of week
        daily_patterns['day_num'] = daily_patterns['day'].map(day_order)
        daily_patterns = daily_patterns.sort_values('day_num').drop('day_num', axis=1)
        
        return daily_patterns
    
    def identify_traffic_hotspots(self, days_back=30):
        """
        Identify traffic hotspots based on historical data
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            DataFrame with locations ranked by traffic severity
        """
        # Get historical data for all locations
        df = self._get_historical_data(days_back)
        
        if df.empty:
            return pd.DataFrame()
            
        # Calculate traffic index
        df['traffic_index'] = df.apply(
            lambda row: max(0, min(100, int(100 * (1 - row['current_speed'] / row['free_flow_speed']))))
            if row['free_flow_speed'] > 0 and row['current_speed'] > 0 else 0, 
            axis=1
        )
        
        # Group by location and calculate averages
        hotspots = df.groupby('point_name').agg({
            'traffic_index': 'mean',
            'current_speed': 'mean',
            'free_flow_speed': 'mean',
            'traffic_incidents': 'mean',
            'latitude': 'first',
            'longitude': 'first'
        }).reset_index()
        
        # Sort by traffic index (highest first)
        hotspots = hotspots.sort_values('traffic_index', ascending=False)
        
        return hotspots
    
    def generate_heatmap_data(self, days_back=30):
        """
        Generate data for creating a traffic heatmap
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            DataFrame with location and severity data for heatmap
        """
        # Get hotspot data
        hotspots = self.identify_traffic_hotspots(days_back)
        
        if hotspots.empty:
            return pd.DataFrame()
        
        # Keep only necessary columns and ensure proper format
        heatmap_data = hotspots[['point_name', 'latitude', 'longitude', 'traffic_index']]
        
        return heatmap_data
    
    def identify_recurring_patterns(self, days_back=30, n_clusters=3):
        """
        Use clustering to identify recurring traffic patterns
        
        Args:
            days_back: Number of days to look back
            n_clusters: Number of pattern clusters to identify
            
        Returns:
            Dictionary with cluster information and visualizations
        """
        # Get historical data
        df = self._get_historical_data(days_back)
        
        if df.empty or len(df) < n_clusters:
            return {"error": "Not enough data for clustering"}
            
        # Convert timestamp to datetime and extract features
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Calculate traffic index
        df['traffic_index'] = df.apply(
            lambda row: max(0, min(100, int(100 * (1 - row['current_speed'] / row['free_flow_speed']))))
            if row['free_flow_speed'] > 0 and row['current_speed'] > 0 else 0, 
            axis=1
        )
        
        # Select features for clustering
        features = df[['hour', 'day_of_week', 'traffic_index', 'traffic_incidents']]
        
        # Standardize features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        # Perform clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        df['cluster'] = kmeans.fit_predict(scaled_features)
        
        # Analyze clusters
        cluster_stats = df.groupby('cluster').agg({
            'traffic_index': 'mean',
            'current_speed': 'mean',
            'hour': ['mean', 'median'],
            'day_of_week': ['mean', 'median'],
            'traffic_incidents': 'mean'
        }).reset_index()
        
        # Map day of week numbers to names
        day_names = {i: day for i, day in enumerate(calendar.day_name)}
        cluster_stats['common_day'] = cluster_stats[('day_of_week', 'median')].apply(
            lambda x: day_names[int(x % 7)]
        )
        
        # Create descriptions
        descriptions = []
        for _, row in cluster_stats.iterrows():
            hour = int(row[('hour', 'median')])
            time_of_day = "Morning" if 5 <= hour < 12 else "Afternoon" if 12 <= hour < 17 else "Evening" if 17 <= hour < 22 else "Night"
            day = row['common_day']
            traffic_level = "Heavy" if row[('traffic_index', 'mean')] > 60 else "Moderate" if row[('traffic_index', 'mean')] > 30 else "Light"
            
            desc = f"{traffic_level} traffic during {time_of_day} hours on {day}s"
            descriptions.append(desc)
        
        # Add descriptions to cluster stats
        cluster_stats['description'] = descriptions
        
        return {
            "cluster_stats": cluster_stats,
            "cluster_data": df
        }
    
    def _get_historical_data(self, days_back=30, location=None):
        """
        Retrieve historical traffic data from the database
        
        Args:
            days_back: Number of days to look back
            location: Optional location filter
            
        Returns:
            DataFrame with historical traffic data
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                start_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
                
                query = f"""
                    SELECT * FROM traffic_data 
                    WHERE timestamp > '{start_date}'
                """
                
                if location:
                    query += f" AND point_name = '{location}'"
                    
                query += " ORDER BY timestamp"
                
                return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"Error retrieving historical data: {e}")
            return pd.DataFrame()

    def plot_hourly_pattern(self, location=None, days_back=30):
        """Generate an hourly pattern plot for a specific location or all locations"""
        hourly_data = self.get_hourly_patterns(days_back, location)
        
        if hourly_data.empty:
            return None
            
        title = f"Hourly Traffic Pattern - {'All Locations' if not location else location}"
        fig = px.line(
            hourly_data, 
            x="hour", 
            y="traffic_index",
            title=title,
            labels={"hour": "Hour of Day", "traffic_index": "Traffic Index (0-100)"}
        )
        
        fig.update_layout(
            xaxis=dict(tickmode='linear', tick0=0, dtick=2)
        )
        
        return fig
        
    def plot_daily_pattern(self, location=None, days_back=90):
        """Generate a daily pattern plot for a specific location or all locations"""
        daily_data = self.get_daily_patterns(days_back, location)
        
        if daily_data.empty:
            return None
            
        title = f"Daily Traffic Pattern - {'All Locations' if not location else location}"
        fig = px.bar(
            daily_data, 
            x="day", 
            y="traffic_index",
            title=title,
            labels={"day": "Day of Week", "traffic_index": "Traffic Index (0-100)"}
        )
        
        return fig

    def generate_traffic_heatmap(self, days_back=30):
        """Generate a traffic heatmap visualization"""
        heatmap_data = self.generate_heatmap_data(days_back)
        
        if heatmap_data.empty:
            return None
            
        fig = px.scatter_mapbox(
            heatmap_data,
            lat="latitude",
            lon="longitude",
            color="traffic_index",
            size="traffic_index",
            hover_name="point_name",
            color_continuous_scale=px.colors.sequential.Plasma,
            size_max=15,
            zoom=11,
            title="Bengaluru Traffic Hotspots"
        )
        
        fig.update_layout(mapbox_style="open-street-map")
        fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
        
        return fig

if __name__ == "__main__":
    analyzer = TrafficPatternAnalyzer()
    # Example usage
    hourly_patterns = analyzer.get_hourly_patterns()
    print(hourly_patterns.head())
