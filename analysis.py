import os
import geopandas as gpd
import networkx as nx
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from sklearn.neighbors import BallTree
from sklearn.linear_model import LogisticRegression
import folium
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
import streamlit as st
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

# --- Streamlit Page Config (Must be first) ---
st.set_page_config(layout="wide", page_title="Bengaluru Metro Analysis")

class ComprehensiveMetroAnalyzer:
    """
    Final, correct, and optimized metro expansion prediction and analysis system.
    """
    
    def __init__(self, road_network_file='road_network.geojson', data_path='.'):
        self.road_network_file = road_network_file
        self.data_path = data_path
        self.G = None
        self.snaps = {}
        self.ts = None
        self.model = None
        self.predictions = {}
        
    def build_road_graph(self):
        print("Building road network graph...")
        roads = gpd.read_file(self.road_network_file)
        self.G = nx.Graph()
        for r in roads.itertuples():
            geom = getattr(r, 'geometry', None)
            if geom and geom.geom_type == 'LineString':
                prev = None
                for lon, lat in geom.coords:
                    node = (round(lat, 6), round(lon, 6))
                    self.G.add_node(node)
                    if prev:
                        dist = geodesic(prev, node).meters
                        self.G.add_edge(prev, node, weight=dist)
                    prev = node
        print(f"Built road graph: {len(self.G.nodes)} nodes, {len(self.G.edges)} edges")
        return self.G

    def load_historical(self, path, years):
        print("Loading historical metro data...")
        self.snaps = {}
        for y in years:
            f = os.path.join(path, f"static/data/data_{y}.geojson")
            coords = []
            if os.path.exists(f):
                gdf = gpd.read_file(f)
                for _, row in gdf.iterrows():
                    geom = row.geometry
                    if geom.geom_type == 'Point' and (row.get('network') == 'Namma Metro' or row.get('station') == 'subway'):
                        coords.append((geom.y, geom.x))
            self.snaps[y] = coords
            if coords:
                print(f"Loaded {len(coords)} metro stations for {y}")
        return self.snaps

    def build_time_series(self, G, snaps, years):
        print("Building time series...")
        nodes = list(G.nodes)
        idx = pd.MultiIndex.from_product([nodes, years], names=('node','year'))
        ts = pd.DataFrame(0, index=idx, columns=['station'])
        tree, arr = BallTree(np.deg2rad(np.array(nodes)), metric='haversine'), np.array(nodes)
        for y in years:
            coords = snaps[y]
            if coords:
                _, ix = tree.query(np.deg2rad(np.array(coords)), k=1)
                for i in ix.flatten():
                    ts.at[(tuple(arr[i]), y), 'station'] = 1
        return ts

    def train_model(self, ts, years):
        print(f"Training model up to {years[-1]}...")
        rows = []
        for node in ts.index.levels[0]:
            s = ts.xs(node, level=0)['station']
            cum = 0
            for y1, y2 in zip(years, years[1:]):
                cum += s.get(y1, 0)
                rows.append({'past': cum, 'year': y1, 'target': s.get(y2, 0)})
        df = pd.DataFrame(rows)
        if df['target'].nunique() < 2:
            return None
        return LogisticRegression(solver='liblinear').fit(df[['past','year']].values, df['target'].values)

    def predict_lines(self, G, model, ts, year, start_year, count, min_dist, global_nodes):
        cand, sel, lines = [], [], []
        for node in G.nodes:
            if node in global_nodes: continue
            past = ts.xs(node, level=0)['station'].loc[start_year:year-1].sum()
            if past > 0: continue
            p = model.predict_proba([[past, year]])[0,1] if model else 0
            cand.append((node, p))
        cand.sort(key=lambda x: -x[1])
        rads = [np.deg2rad(n) for n in global_nodes]
        tree = BallTree(np.array(rads), metric='haversine') if rads else None
        for node, p in cand:
            if len(sel) >= count: break
            rad = np.deg2rad(node)
            if tree:
                d = tree.query([rad], k=1)[0][0][0] * 6371000
                if d < min_dist: continue
            sel.append((node, p))
            rads.append(rad)
            tree = BallTree(np.array(rads), metric='haversine')
        prev = global_nodes[-1] if global_nodes else None
        for node, _ in sel:
            if prev and nx.has_path(G, prev, node):
                try: lines.append(nx.shortest_path(G, prev, node, weight='weight'))
                except: lines.append([])
            else: lines.append([])
            prev = node
        return sel, lines

    def get_bus_stops_coords(self, bus_file='static/data/data_2025.geojson'):
        gdf = gpd.read_file(bus_file)
        bus_coords = []
        for _, row in gdf.iterrows():
            if (row.get('highway') == 'bus_stop' and hasattr(row, 'geometry') and row.geometry.geom_type == 'Point'):
                bus_coords.append((row.geometry.y, row.geometry.x))
        return np.array(bus_coords)

    def analyze_metro_feeder_needs(self, metro_stations_coords, bus_stops_coords, top_n=100):
        if len(metro_stations_coords) == 0: return []
        if len(bus_stops_coords) == 0:
            print("Warning: No bus stops found for feeder analysis.")
            return []

        metro_coords_np = np.array(metro_stations_coords)
        bus_tree = BallTree(np.deg2rad(bus_stops_coords), metric='haversine')
        
        distances, _ = bus_tree.query(np.deg2rad(metro_coords_np), k=1)
        min_distances_meters = distances.flatten() * 6371000

        metro_feeder_needs = []
        for i, metro_coord in enumerate(metro_stations_coords):
            metro_feeder_needs.append({
                'coordinates': metro_coord,
                'distance_to_nearest_bus_stop': min_distances_meters[i]
            })
        
        return sorted(metro_feeder_needs, key=lambda x: x['distance_to_nearest_bus_stop'], reverse=True)[:top_n]


@st.cache_data
def run_full_analysis():
    analyzer = ComprehensiveMetroAnalyzer()
    
    history_years = list(range(2017, 2026))
    future_years = list(range(2026, 2036))
    
    G = analyzer.build_road_graph()
    snaps = analyzer.load_historical('.', history_years + [2025])
    ts = analyzer.build_time_series(G, snaps, history_years)
    model = analyzer.train_model(ts, history_years)
    print("Initial model trained successfully.")
    
    preds, lines = [], []
    global_nodes = [n for n, s in ts.xs(2025, level=1)['station'].items() if s==1]
    
    total_needed = max(1, int(len(G.nodes) * 0.02))
    per_year = total_needed // len(future_years)
    remaining = total_needed % len(future_years)
    
    history = list(history_years)
    all_predictions_data = {} 
    
    for i, y in enumerate(future_years):
        count = per_year + (1 if i < remaining else 0)
        sel, ln = analyzer.predict_lines(G, model, ts, y, history[0], count, 1000, global_nodes)
        
        preds.append(sel)
        lines.append(ln)
        all_predictions_data[y] = sel
        
        global_nodes.extend([node for node,_ in sel])
        new_data = pd.DataFrame({'station':1}, index=pd.MultiIndex.from_product([[n for n,_ in sel], [y]], names=('node','year')))
        ts = pd.concat([ts, new_data])
        history.append(y)
        model = analyzer.train_model(ts, history) or model
    
    bus_stops_coords = analyzer.get_bus_stops_coords()
    
    metro_2025_coords = snaps[2025]
    farthest_metro_2025 = analyzer.analyze_metro_feeder_needs(metro_2025_coords, bus_stops_coords, top_n=100)
    
    metro_2031_coords = [node for node, _ in all_predictions_data.get(2031, [])]
    farthest_metro_2031 = analyzer.analyze_metro_feeder_needs(metro_2031_coords, bus_stops_coords, top_n=100)
    
    return preds, lines, future_years, farthest_metro_2025, farthest_metro_2031, all_predictions_data, snaps

def create_dashboard(preds, lines, future_years, farthest_metro_2025, farthest_metro_2031, all_predictions_data, snaps):
    st.title("Bengaluru Metro & Feeder Integration Analysis")
    st.header("Identifying Metro Stations Most in Need of Feeder Connectivity")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Metro Network Map with Feeder Needs")
        
        m = folium.Map(location=[12.9716, 77.5946], zoom_start=10)
        
        # Layer for the Consolidated 2025-2035 Network
        consolidated_layer = folium.FeatureGroup(name="Consolidated Network (2025-2035)", show=True)
        
        # Add 2025 metro stations to this layer
        if 2025 in snaps:
            for station in snaps[2025]:
                folium.CircleMarker(
                    location=station,
                    radius=5,
                    color='blue',
                    fill=True,
                    popup="Existing 2025 Station"
                ).add_to(consolidated_layer)
        
        # Add all predicted stations (2026-2035) to this layer
        for year_preds in preds:
            for node, prob in year_preds:
                folium.CircleMarker(
                    location=node,
                    radius=5,
                    color='red',
                    fill=True,
                    popup=f"Predicted Station: Prob {prob:.3f}"
                ).add_to(consolidated_layer)
        
        consolidated_layer.add_to(m)

        # Layer for 2025 Metro Stations needing feeders (Orange)
        if farthest_metro_2025:
            feeder_2025_layer = folium.FeatureGroup(name="Feeder Need (Existing 2025 Metro)", show=True)
            for metro in farthest_metro_2025:
                folium.CircleMarker(
                    location=metro['coordinates'],
                    radius=8,
                    color='orange',
                    fill=True,
                    fillOpacity=0.8,
                    popup=f"Metro Station (2025): {metro['distance_to_nearest_bus_stop']:.0f}m from nearest bus stop"
                ).add_to(feeder_2025_layer)
                folium.Circle(
                    location=metro['coordinates'],
                    radius=metro['distance_to_nearest_bus_stop'],
                    color='orange',
                    fill=False,
                    weight=2,
                    dash_array='5, 5'
                ).add_to(feeder_2025_layer)
            feeder_2025_layer.add_to(m)

        # Layer for 2031 Predicted Stations needing feeders (Green)
        if farthest_metro_2031:
            feeder_2031_layer = folium.FeatureGroup(name="Feeder Need (Predicted 2031 Metro)", show=True)
            for metro in farthest_metro_2031:
                folium.CircleMarker(
                    location=metro['coordinates'],
                    radius=8,
                    color='green',
                    fill=True,
                    fillOpacity=0.8,
                    popup=f"Metro Station (2031): {metro['distance_to_nearest_bus_stop']:.0f}m from nearest bus stop"
                ).add_to(feeder_2031_layer)
                folium.Circle(
                    location=metro['coordinates'],
                    radius=metro['distance_to_nearest_bus_stop'],
                    color='green',
                    fill=False,
                    weight=2,
                    dash_array='5, 5'
                ).add_to(feeder_2031_layer)
            feeder_2031_layer.add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, width=900, height=700)
    
    with col2:
        st.header("Feeder Analysis Summary")
        
        st.metric("Total Stations in 2031 Prediction", len(all_predictions_data.get(2031, [])))
        st.metric("Top 100 Feeder-Needy Stations (2031)", len(farthest_metro_2031))
        st.metric("Top 100 Feeder-Needy Stations (2025)", len(farthest_metro_2025))

        st.subheader("Distribution of Isolation for 2031's Neediest Metro Stations")
        if farthest_metro_2031:
            distances_2031 = [m['distance_to_nearest_bus_stop'] for m in farthest_metro_2031]
            fig, ax = plt.subplots()
            ax.hist(distances_2031, bins=20, color='green', edgecolor='black')
            ax.set_xlabel('Distance to Nearest Bus Stop (meters)')
            ax.set_ylabel('Count of Metro Stations')
            st.pyplot(fig)
        
        st.subheader("Distribution of Isolation for 2025's Neediest Metro Stations")
        if farthest_metro_2025:
            distances_2025 = [m['distance_to_nearest_bus_stop'] for m in farthest_metro_2025]
            fig2, ax2 = plt.subplots()
            ax2.hist(distances_2025, bins=20, color='orange', edgecolor='black')
            ax2.set_xlabel('Distance to Nearest Bus Stop (meters)')
            ax2.set_ylabel('Count of Metro Stations')
            st.pyplot(fig2)

if __name__ == '__main__':
    # --- FIX: Unpack the correct number of values ---
    preds_data, lines_data, future_years_data, farthest_metro_2025_data, farthest_metro_2031_data, all_predictions_data, snaps_data = run_full_analysis()
    
    # --- FIX: Pass the correct number of arguments to the dashboard function ---
    create_dashboard(preds_data, lines_data, future_years_data, farthest_metro_2025_data, farthest_metro_2031_data, all_predictions_data, snaps_data)
