import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from bmtc_analyzer import BMTCAnalyzer
from traffic_alerts import check_alerts
from traffic_analyzer import TrafficAnalyzer
from traffic_patterns import TrafficPatternAnalyzer

# Set page config
st.set_page_config(
    page_title="Bengaluru Traffic Dashboard",
    page_icon="🚦",
    layout="wide"
)

# Initialize session state
if 'bmtc_analyzer' not in st.session_state:
    st.session_state.bmtc_analyzer = BMTCAnalyzer()
    st.session_state.bmtc_analyzer.load_data()

# Initialize traffic analyzer
if 'traffic_analyzer' not in st.session_state:
    st.session_state.traffic_analyzer = TrafficAnalyzer()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_recent_traffic_data(hours: int = 24) -> pd.DataFrame:
    """Get recent traffic data from the database"""
    try:
        with sqlite3.connect("traffic_data.db") as conn:
            query = """
                SELECT timestamp, latitude, longitude, traffic_index 
                FROM traffic_data 
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
            """
            df = pd.read_sql_query(query, conn, params=(f"-{hours} hours",))
            return df
    except Exception as e:
        st.error(f"Error loading traffic data: {str(e)}")
        return pd.DataFrame()

def show_bmtc_analysis():
    """Display BMTC analysis section"""
    st.header("🚌 BMTC Bus Stop Analysis")
    
    # Get recent traffic data
    traffic_data = get_recent_traffic_data()
    
    # Create two columns for the layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Show map with bus stops
        st.subheader("Bus Stop Map")
        m = st.session_state.bmtc_analyzer.create_bus_stop_map()
        if m:
            folium_static(m, width=800, height=600)
        else:
            st.warning("Could not create bus stop map")
    
    with col2:
        # Show traffic impact analysis
        st.subheader("Traffic Impact")
        if not traffic_data.empty:
            impact = st.session_state.bmtc_analyzer.correlate_with_traffic(traffic_data)
            if not impact.empty:
                # Show top 10 most affected stops
                st.write("Most Affected Stops")
                top_affected = impact.nlargest(10, 'avg_traffic')
                st.dataframe(top_affected[['name', 'avg_traffic']].rename(
                    columns={'name': 'Stop', 'avg_traffic': 'Avg Traffic'}
                ))
                
                # Show statistics
                st.metric("Total Bus Stops", len(st.session_state.bmtc_analyzer.bus_stops))
                st.metric("Stops with Traffic Data", len(impact[~impact['avg_traffic'].isna()]))
            else:
                st.info("No traffic impact data available")
        else:
            st.info("No recent traffic data available")
    
    # Show nearby stops for a selected location
    st.subheader("Find Stops Near Location")
    col1, col2 = st.columns(2)
    
    with col1:
        lat = st.number_input("Latitude", value=12.9716, format="%.6f")
        lon = st.number_input("Longitude", value=77.5946, format="%.6f")
        radius = st.slider("Radius (km)", 0.1, 5.0, 0.5, 0.1)
    
    if st.button("Find Nearby Stops"):
        nearby = st.session_state.bmtc_analyzer.get_nearby_stops((lat, lon), radius)
        
        if not nearby.empty:
            st.write(f"Found {len(nearby)} stops within {radius}km")
            st.map(nearby[['latitude', 'longitude']])
            st.dataframe(nearby[['name', 'latitude', 'longitude']])
        else:
            st.warning("No stops found in the specified area")

def show_traffic_overview():
    """Display main traffic overview"""
    st.header("🚦 Traffic Overview")
    
    # Get recent traffic data
    traffic_data = get_recent_traffic_data()
    
    if not traffic_data.empty:
        # Show traffic map
        st.subheader("Live Traffic Map")
        st.map(traffic_data[['latitude', 'longitude']])
        
        # Show traffic alerts
        st.subheader("Traffic Alerts")
        alerts = check_alerts()
        if alerts:
            for alert in alerts:
                st.warning(f"🚨 {alert}")
        else:
            st.info("No active traffic alerts")
            
        # Show traffic patterns
        st.subheader("Traffic Patterns")
        pattern_analyzer = TrafficPatternAnalyzer()
        fig = pattern_analyzer.plot_hourly_pattern()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No recent traffic data available")

def main():
    """Main dashboard function"""
    st.title("🚦 Bengaluru Traffic & Transport Dashboard")
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Traffic Overview", "BMTC Analysis"]
    )
    
    if page == "Traffic Overview":
        show_traffic_overview()
    elif page == "BMTC Analysis":
        show_bmtc_analysis()

if __name__ == "__main__":
    main()
