"""
Transport Impact Analysis Module
Correlates traffic data with BMTC public transport data
"""
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
from pathlib import Path
import math
from haversine import haversine

# Load environment variables
load_dotenv()

class TransportImpactAnalyzer:
    """Analyzes the impact of traffic on public transportation and vice versa"""
    
    def __init__(self, traffic_db="traffic_data.db", gtfs_dir="./gtfs_data"):
        """Initialize the transport impact analyzer"""
        self.traffic_db = traffic_db
        self.gtfs_dir = gtfs_dir
        
        # Create directory for GTFS data if it doesn't exist
        os.makedirs(self.gtfs_dir, exist_ok=True)
        
        # Initialize GTFS database tables if needed
        self._init_gtfs_tables()
        
    def _init_gtfs_tables(self):
        """Initialize tables for GTFS data in the database"""
        with sqlite3.connect(self.traffic_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gtfs_stops (
                    stop_id TEXT PRIMARY KEY,
                    stop_name TEXT,
                    stop_lat REAL,
                    stop_lon REAL,
                    closest_monitor_point TEXT,
                    distance_to_monitor REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gtfs_delays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id TEXT,
                    route_id TEXT,
                    stop_id TEXT,
                    scheduled_time TEXT,
                    actual_time TEXT, 
                    delay_seconds INTEGER,
                    traffic_index REAL,
                    incident_count INTEGER,
                    timestamp TEXT
                )
            ''')
            
            conn.commit()
    
    def import_gtfs_data(self, force_reload=False):
        """
        Import BMTC GTFS data from files
        
        Args:
            force_reload: Whether to force reload data even if it exists
        """
        # Check if data already exists
        with sqlite3.connect(self.traffic_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM gtfs_stops")
            count = cursor.fetchone()[0]
            
            if count > 0 and not force_reload:
                print(f"GTFS data already imported ({count} stops). Use force_reload=True to reimport.")
                return
        
        # Check for GTFS files
        stops_file = os.path.join(self.gtfs_dir, "stops.txt")
        
        if not os.path.exists(stops_file):
            print(f"GTFS files not found in {self.gtfs_dir}. Please download from BMTC.")
            return
        
        # Import stops data
        stops_df = pd.read_csv(stops_file)
        
        # Map stops to nearest traffic monitoring points
        monitor_points = self._get_monitor_points()
        stops_df['closest_monitor_point'] = None
        stops_df['distance_to_monitor'] = None
        
        for i, stop in stops_df.iterrows():
            closest, distance = self._find_closest_point(
                stop['stop_lat'], stop['stop_lon'], 
                monitor_points
            )
            stops_df.at[i, 'closest_monitor_point'] = closest
            stops_df.at[i, 'distance_to_monitor'] = distance
        
        # Save to database
        with sqlite3.connect(self.traffic_db) as conn:
            stops_df.to_sql('gtfs_stops', conn, if_exists='replace', index=False)
            
        print(f"Imported {len(stops_df)} BMTC bus stops")
    
    def _get_monitor_points(self):
        """Get monitor points from the database"""
        with sqlite3.connect(self.traffic_db) as conn:
            query = """
                SELECT DISTINCT point_name, latitude, longitude 
                FROM traffic_data
            """
            return pd.read_sql_query(query, conn)
    
    def _find_closest_point(self, lat, lon, points_df):
        """Find the closest monitoring point to a given location"""
        if points_df.empty:
            return None, None
            
        closest = None
        min_distance = float('inf')
        
        for _, point in points_df.iterrows():
            distance = haversine(
                (lat, lon), 
                (point['latitude'], point['longitude']),
                unit='km'
            )
            
            if distance < min_distance:
                min_distance = distance
                closest = point['point_name']
                
        return closest, min_distance
    
    def import_transit_delays(self, delays_file):
        """
        Import transit delay data from CSV file
        
        Args:
            delays_file: Path to CSV file with delay information
        """
        if not os.path.exists(delays_file):
            print(f"Delays file not found: {delays_file}")
            return
            
        delays_df = pd.read_csv(delays_file)
        required_cols = ['trip_id', 'route_id', 'stop_id', 'scheduled_time', 'actual_time']
        
        for col in required_cols:
            if col not in delays_df.columns:
                print(f"Required column missing from delays file: {col}")
                return
        
        # Calculate delay in seconds
        delays_df['scheduled_time'] = pd.to_datetime(delays_df['scheduled_time'])
        delays_df['actual_time'] = pd.to_datetime(delays_df['actual_time'])
        delays_df['delay_seconds'] = (delays_df['actual_time'] - delays_df['scheduled_time']).dt.total_seconds()
        
        # Get traffic conditions for each delay record
        stops_info = self._get_stops_info()
        
        # Merge to get closest monitor point for each stop
        delays_df = delays_df.merge(
            stops_info[['stop_id', 'closest_monitor_point']], 
            on='stop_id', 
            how='left'
        )
        
        # Add traffic information
        delays_df['traffic_index'] = None
        delays_df['incident_count'] = None
        
        with sqlite3.connect(self.traffic_db) as conn:
            for i, row in delays_df.iterrows():
                if pd.isna(row['closest_monitor_point']):
                    continue
                    
                # Find nearest traffic data point in time
                query = f"""
                    SELECT 
                        current_speed, free_flow_speed, traffic_incidents 
                    FROM 
                        traffic_data 
                    WHERE 
                        point_name = '{row['closest_monitor_point']}' 
                        AND timestamp <= '{row['actual_time'].isoformat()}'
                    ORDER BY 
                        timestamp DESC 
                    LIMIT 1
                """
                
                try:
                    traffic_data = pd.read_sql_query(query, conn)
                    
                    if not traffic_data.empty:
                        row_data = traffic_data.iloc[0]
                        current_speed = row_data['current_speed']
                        free_flow_speed = row_data['free_flow_speed']
                        
                        if current_speed > 0 and free_flow_speed > 0:
                            traffic_index = min(100, max(0, 100 * (1 - current_speed / free_flow_speed)))
                            delays_df.at[i, 'traffic_index'] = traffic_index
                            
                        delays_df.at[i, 'incident_count'] = row_data['traffic_incidents']
                except Exception as e:
                    print(f"Error getting traffic data: {e}")
        
        # Save to database
        with sqlite3.connect(self.traffic_db) as conn:
            delays_df['timestamp'] = datetime.now().isoformat()
            
            # Select relevant columns
            save_cols = [
                'trip_id', 'route_id', 'stop_id', 
                'scheduled_time', 'actual_time', 'delay_seconds',
                'traffic_index', 'incident_count', 'timestamp'
            ]
            
            delays_df[save_cols].to_sql('gtfs_delays', conn, if_exists='append', index=False)
            
        print(f"Imported {len(delays_df)} transit delay records")
    
    def _get_stops_info(self):
        """Get GTFS stops information"""
        with sqlite3.connect(self.traffic_db) as conn:
            return pd.read_sql("SELECT * FROM gtfs_stops", conn)
    
    def analyze_traffic_impact(self, days_back=30):
        """
        Analyze the impact of traffic conditions on transit delays
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            DataFrame with impact analysis results
        """
        with sqlite3.connect(self.traffic_db) as conn:
            # Get delay data with matching traffic conditions
            query = f"""
                SELECT 
                    d.route_id, d.delay_seconds, d.traffic_index, d.incident_count,
                    s.stop_name, s.closest_monitor_point
                FROM 
                    gtfs_delays d
                JOIN 
                    gtfs_stops s ON d.stop_id = s.stop_id
                WHERE 
                    d.traffic_index IS NOT NULL
                    AND d.timestamp >= datetime('now', '-{days_back} days')
            """
            
            data = pd.read_sql_query(query, conn)
            
        if data.empty:
            print("No matching data found for analysis")
            return pd.DataFrame()
        
        # Group by traffic conditions and analyze delays
        # Bin traffic index into categories
        data['traffic_category'] = pd.cut(
            data['traffic_index'], 
            bins=[0, 20, 40, 60, 80, 100],
            labels=['Very Light', 'Light', 'Moderate', 'Heavy', 'Very Heavy']
        )
        
        # Calculate average delay by traffic category
        impact_analysis = data.groupby('traffic_category').agg({
            'delay_seconds': ['count', 'mean', 'median', 'std'],
            'traffic_index': 'mean'
        }).reset_index()
        
        # Flatten the MultiIndex columns
        impact_analysis.columns = [
            'traffic_category', 'count', 'avg_delay', 'median_delay', 
            'std_delay', 'avg_traffic_index'
        ]
        
        # Sort by traffic impact
        impact_analysis = impact_analysis.sort_values('avg_traffic_index')
        
        return impact_analysis
    
    def analyze_route_vulnerability(self, top_n=10):
        """
        Analyze which routes are most vulnerable to traffic conditions
        
        Args:
            top_n: Number of top routes to return
            
        Returns:
            DataFrame with route vulnerability analysis
        """
        with sqlite3.connect(self.traffic_db) as conn:
            query = """
                SELECT 
                    d.route_id, 
                    COUNT(*) as total_trips,
                    AVG(d.delay_seconds) as avg_delay,
                    AVG(d.traffic_index) as avg_traffic_index,
                    CORR(d.delay_seconds, d.traffic_index) as delay_traffic_correlation
                FROM 
                    gtfs_delays d
                WHERE 
                    d.traffic_index IS NOT NULL
                GROUP BY 
                    d.route_id
                HAVING 
                    COUNT(*) >= 5
            """
            
            route_analysis = pd.read_sql_query(query, conn)
            
        if route_analysis.empty:
            print("No route data available for vulnerability analysis")
            return pd.DataFrame()
        
        # Add vulnerability score based on correlation and average delay
        route_analysis['vulnerability_score'] = route_analysis['delay_traffic_correlation'] * np.log1p(route_analysis['avg_delay'])
        
        # Sort by vulnerability score
        route_analysis = route_analysis.sort_values('vulnerability_score', ascending=False).head(top_n)
        
        return route_analysis
    
    def plot_traffic_delay_correlation(self):
        """
        Generate a plot showing the correlation between traffic and delays
        
        Returns:
            Plotly figure object
        """
        with sqlite3.connect(self.traffic_db) as conn:
            query = """
                SELECT 
                    delay_seconds, traffic_index
                FROM 
                    gtfs_delays
                WHERE 
                    traffic_index IS NOT NULL
                    AND delay_seconds BETWEEN -600 AND 1800
            """
            
            data = pd.read_sql_query(query, conn)
            
        if data.empty:
            print("No data available for correlation plot")
            return None
        
        fig = px.scatter(
            data,
            x="traffic_index",
            y="delay_seconds",
            trendline="ols",
            title="Correlation between Traffic Conditions and Bus Delays",
            labels={
                "traffic_index": "Traffic Index (0-100)",
                "delay_seconds": "Delay (seconds)"
            }
        )
        
        return fig
    
    def generate_impact_dashboard(self):
        """
        Generate dashboard data for visualizing traffic impact on transportation
        
        Returns:
            Dictionary with dashboard data
        """
        # Get overall impact metrics
        impact_analysis = self.analyze_traffic_impact()
        vulnerable_routes = self.analyze_route_vulnerability()
        correlation_plot = self.plot_traffic_delay_correlation()
        
        return {
            "impact_analysis": impact_analysis,
            "vulnerable_routes": vulnerable_routes,
            "correlation_plot": correlation_plot,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

if __name__ == "__main__":
    analyzer = TransportImpactAnalyzer()
    # Example usage: import data and run analysis
    # analyzer.import_gtfs_data()
    # analyzer.analyze_traffic_impact()
