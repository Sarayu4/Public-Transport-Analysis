"""
Traffic Alerts Module for Bengaluru Traffic Monitoring System
"""
import os
import smtplib
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from traffic_config import MONITOR_POINTS

# Load environment variables
load_dotenv()

class TrafficAlertSystem:
    """System for detecting severe traffic conditions and sending alerts"""
    
    def __init__(self, db_path="traffic_data.db"):
        """Initialize the alert system"""
        self.db_path = db_path
        self.email_sender = os.getenv("EMAIL_SENDER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.alert_recipients = os.getenv("ALERT_RECIPIENTS", "").split(",")
        
        # Alert thresholds
        self.severe_congestion_threshold = 80  # Traffic index above 80 is severe
        self.high_incident_threshold = 3       # More than 3 incidents is concerning
        self.speed_reduction_threshold = 0.4   # Less than 40% of free flow speed is severe
        
        # Create alert history table
        self._init_alert_db()
    
    def _init_alert_db(self):
        """Initialize the alerts database table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS traffic_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    point_name TEXT,
                    alert_type TEXT,
                    severity INTEGER,
                    message TEXT,
                    timestamp TEXT,
                    notified INTEGER
                )
            ''')
            conn.commit()
    
    def check_for_alerts(self):
        """Check for severe traffic conditions"""
        print(f"🔔 Checking for traffic alerts at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        alerts = []
        
        # Get recent traffic data
        recent_data = self._get_recent_traffic_data()
        
        if recent_data.empty:
            print("No recent data available for alert analysis")
            return
        
        # Check for severe congestion
        for _, row in recent_data.iterrows():
            point_name = row['point_name']
            current_speed = row.get('current_speed', 0)
            free_flow_speed = row.get('free_flow_speed', 0)
            incidents = row.get('traffic_incidents', 0)
            
            # Calculate traffic index (0-100, higher is worse)
            if free_flow_speed > 0 and current_speed > 0:
                speed_ratio = current_speed / free_flow_speed
                traffic_index = max(0, min(100, 100 * (1 - speed_ratio)))
            else:
                traffic_index = 0
                
            # Check conditions and create alerts
            if traffic_index >= self.severe_congestion_threshold:
                severity = min(int(traffic_index / 10), 10)  # 1-10 scale
                message = f"Severe congestion detected at {point_name}. Traffic index: {traffic_index:.1f}"
                alerts.append({
                    'point_name': point_name,
                    'alert_type': 'CONGESTION',
                    'severity': severity,
                    'message': message
                })
                
            if incidents >= self.high_incident_threshold:
                severity = min(incidents, 10)  # 1-10 scale
                message = f"{incidents} traffic incidents reported near {point_name}"
                alerts.append({
                    'point_name': point_name,
                    'alert_type': 'INCIDENTS',
                    'severity': severity,
                    'message': message
                })
                
            # Speed reduction alert
            if free_flow_speed > 0 and current_speed > 0:
                if current_speed / free_flow_speed <= self.speed_reduction_threshold:
                    severity = min(int((1 - current_speed / free_flow_speed) * 10), 10)
                    reduction_percent = 100 * (1 - current_speed / free_flow_speed)
                    message = f"Significant speed reduction at {point_name}. {reduction_percent:.1f}% below free flow speed"
                    alerts.append({
                        'point_name': point_name,
                        'alert_type': 'SPEED_REDUCTION',
                        'severity': severity,
                        'message': message
                    })
        
        # Process alerts
        if alerts:
            self._save_alerts(alerts)
            if self.email_sender and self.email_password and self.alert_recipients:
                self._send_alert_email(alerts)
            else:
                print("Email configuration not complete. Alerts saved but not sent.")
        else:
            print("No traffic alerts detected")
            
        return alerts
    
    def _get_recent_traffic_data(self):
        """Get traffic data from the last hour"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                query = f"""
                    SELECT * FROM traffic_data 
                    WHERE timestamp > '{one_hour_ago}' 
                    ORDER BY timestamp DESC
                """
                return pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"Error getting recent traffic data: {e}")
            return pd.DataFrame()
    
    def _save_alerts(self, alerts):
        """Save alerts to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.utcnow().isoformat()
                
                for alert in alerts:
                    cursor.execute('''
                        INSERT INTO traffic_alerts 
                        (point_name, alert_type, severity, message, timestamp, notified)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        alert['point_name'],
                        alert['alert_type'],
                        alert['severity'],
                        alert['message'],
                        timestamp,
                        0
                    ))
                
                conn.commit()
                print(f"Saved {len(alerts)} alerts to database")
        except Exception as e:
            print(f"Error saving alerts: {e}")
    
    def _send_alert_email(self, alerts):
        """Send email alerts for severe traffic conditions"""
        if not alerts:
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = ", ".join(self.alert_recipients)
            msg['Subject'] = f"🚨 Bengaluru Traffic Alert - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Create email body
            body = f"<h2>Bengaluru Traffic Alerts</h2>"
            body += f"<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
            body += "<h3>Critical Conditions:</h3>"
            body += "<ul>"
            
            # Sort alerts by severity
            sorted_alerts = sorted(alerts, key=lambda x: x['severity'], reverse=True)
            
            for alert in sorted_alerts:
                severity_stars = "⭐" * alert['severity']
                body += f"<li><strong>{alert['point_name']}:</strong> {alert['message']} {severity_stars}</li>"
            
            body += "</ul>"
            body += "<p>This is an automated message from the Bengaluru Traffic Monitoring System.</p>"
            
            msg.attach(MIMEText(body, 'html'))
            
            # Connect to SMTP server and send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
                
            print(f"✅ Alert email sent to {len(self.alert_recipients)} recipients")
            
            # Update notification status
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.utcnow().isoformat()
                
                for alert in alerts:
                    cursor.execute('''
                        UPDATE traffic_alerts SET notified = 1 
                        WHERE point_name = ? AND alert_type = ? AND timestamp = ?
                    ''', (alert['point_name'], alert['alert_type'], timestamp))
                
                conn.commit()
                
        except Exception as e:
            print(f"Error sending email alert: {e}")

if __name__ == "__main__":
    alert_system = TrafficAlertSystem()
    alert_system.check_for_alerts()
