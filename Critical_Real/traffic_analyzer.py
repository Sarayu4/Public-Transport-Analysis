import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

class TrafficAnalyzer:
    def __init__(self, db_path: str = "traffic_data.db"):
        self.db_path = db_path
    
    def get_recent_data(self, hours: int = 24) -> pd.DataFrame:
        """Get traffic data from the last N hours"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT * FROM traffic_data 
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
            '''
            df = pd.read_sql_query(query, conn, params=(f"-{hours} hours",),
                                 parse_dates=['timestamp'])
        return df
    
    def get_traffic_trends(self, point_name: str = None, days: int = 7) -> Dict[str, Any]:
        """Get traffic trends for a specific point or all points"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT 
                    point_name,
                    date(timestamp) as date,
                    strftime('%H', timestamp) as hour,
                    AVG(current_speed) as avg_speed,
                    AVG(free_flow_speed) as avg_free_flow,
                    AVG(traffic_incidents) as avg_incidents,
                    COUNT(*) as data_points
                FROM traffic_data
                WHERE timestamp >= date('now', ?)
                {point_filter}
                GROUP BY point_name, date, hour
                ORDER BY point_name, date, hour
            '''
            
            params = [f"-{days} days"]
            
            if point_name:
                query = query.format(point_filter="AND point_name = ?")
                params.append(point_name)
            else:
                query = query.format(point_filter="")
            
            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])
        
        # Calculate traffic index (0-100, higher is worse)
        if not df.empty:
            df['traffic_index'] = 100 * (1 - (df['avg_speed'] / df['avg_free_flow']))
            df['traffic_index'] = df['traffic_index'].clip(0, 100)
        
        return df
    
    def get_worst_performing_routes(self, limit: int = 5) -> pd.DataFrame:
        """Get routes with worst traffic conditions"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT 
                    point_name,
                    AVG(current_speed) as avg_speed,
                    AVG(free_flow_speed) as avg_free_flow,
                    AVG(traffic_incidents) as avg_incidents,
                    COUNT(*) as data_points
                FROM traffic_data
                WHERE timestamp >= datetime('now', '-24 hours')
                GROUP BY point_name
                HAVING data_points > 0
                ORDER BY (1 - (AVG(current_speed) / NULLIF(AVG(free_flow_speed), 0))) DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(limit,))
        
        if not df.empty:
            df['traffic_index'] = 100 * (1 - (df['avg_speed'] / df['avg_free_flow']))
            df['traffic_index'] = df['traffic_index'].round(1)
            df['avg_speed'] = df['avg_speed'].round(1)
        
        return df
