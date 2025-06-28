from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
import json
import os


app = Flask(__name__)

# Load GTFS data
stops_df = pd.read_csv("stops.txt")
stop_times_df = pd.read_csv("stop_times.txt")
trips_df = pd.read_csv("trips.txt")
routes_df = pd.read_csv("routes.txt")

# Load or initialize cache
CACHE_FILE = "congestion_cache.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        congestion_cache = json.load(f)
else:
    congestion_cache = {}

cache_hits = 0
api_calls = 0



TOMTOM_API_KEY = "JEj8DXboE7hqN9JtPmkB1tHscL7zpdqi"

# ------------------- ROUTES -------------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/temporal')
def temporal():
    return render_template('temporal.html')

@app.route('/realtime', methods=['GET'])
def realtime():
    stops = sorted(stops_df['stop_name'].unique().tolist())
    return render_template('realtime.html')

@app.route('/realtime-analysis', methods=['POST'])
def realtime_analysis():
    try:
        data = request.get_json()
        source = data.get("source")
        destination = data.get("destination")
        print(f"Fetching route from {source} to {destination}")

        trip_ids = find_routes_between(source, destination)
        if not trip_ids:
            return jsonify({"error": "No routes found between stops."}), 404

        results = evaluate_routes(trip_ids)
        return jsonify(results)

        #results = compute_best_routes(source, destination)
        #return jsonify(results), 200

    except Exception as e:
        print("Error in realtime_analysis:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/critical')
def critical():
    return render_template('critical.html')

@app.route('/forecast')
def forecast():
    return render_template('forecast.html')

@app.route('/api/stops')
def get_all_stops():
    stop_names = sorted(stops_df['stop_name'].unique().tolist())
    return jsonify(stop_names)


# ---------------- HELPER FUNCTIONS -----------------

def get_stop_id_by_name(stop_name):
    match = stops_df[stops_df['stop_name'].str.lower() == stop_name.lower()]
    return match['stop_id'].iloc[0] if not match.empty else None

def find_routes_between(source_name, dest_name):
    source_id = get_stop_id_by_name(source_name)
    dest_id = get_stop_id_by_name(dest_name)
    if not source_id or not dest_id:
        return []
    valid_trips = []
    for trip_id, group in stop_times_df.groupby('trip_id'):
        stop_ids = group.sort_values('stop_sequence')['stop_id'].tolist()
        if source_id in stop_ids and dest_id in stop_ids:
            if stop_ids.index(source_id) < stop_ids.index(dest_id):
                valid_trips.append(trip_id)
    return valid_trips

def get_ordered_stops_for_trip(trip_id):
    trip_stops = stop_times_df[stop_times_df['trip_id'] == trip_id].sort_values('stop_sequence')
    stops_info = []
    for _, row in trip_stops.iterrows():
        stop_data = stops_df[stops_df['stop_id'] == row['stop_id']]
        if not stop_data.empty:
            stop = stop_data.iloc[0]
            try:
                lat = float(stop['stop_lat'])
                lon = float(stop['stop_lon'])
            except:
                continue  # Skip if invalid

            stops_info.append({
                'stop_id': row['stop_id'],
                'stop_name': stop['stop_name'],
                'lat': lat,
                'lon': lon
            })
    return stops_info

# Global counters
cache_hits = 0
api_calls = 0

def get_congestion(lat, lon):
    global cache_hits, api_calls
    key = f"{round(lat, 4)}_{round(lon, 4)}"

    if key in congestion_cache:
        cache_hits += 1
        print(f"[CACHE] Used for {key} (Cache Hits: {cache_hits})")
        return congestion_cache[key]

    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={TOMTOM_API_KEY}"
    
    try:
        res = requests.get(url)
        if res.status_code == 200:
            api_calls += 1
            print(f"[API] Fetching {key} (API Calls: {api_calls})")
            data = res.json()
            cs = data['flowSegmentData']['currentSpeed']
            ffs = data['flowSegmentData']['freeFlowSpeed']
            congestion_cache[key] = (cs, ffs)
            return cs, ffs
        else:
            print(f"[ERROR] API call failed for {key} (status: {res.status_code})")
            return None, None
    except Exception as e:
        print(f"[ERROR] Exception for {key}: {str(e)}")
        return None, None



def evaluate_routes(trip_ids):
    route_scores = []

    for trip_id in trip_ids:
        stops = get_ordered_stops_for_trip(trip_id)
        total_delay = 0
        congestion_values = []

        # Call this here before processing delays
        etas = get_estimated_times(stops)

        for stop in stops:
            current_speed, free_speed = get_congestion(stop['lat'], stop['lon'])

            if current_speed and free_speed and free_speed > 0:
                congestion = max(0, 100 - (current_speed / free_speed * 100))
                congestion_values.append(congestion)
                delay = (1 - current_speed / free_speed) * 1.5
                total_delay += delay

        if congestion_values:
            avg_congestion = sum(congestion_values) / len(congestion_values)
            route_id = trips_df[trips_df['trip_id'] == trip_id]['route_id'].iloc[0]
            route_name = routes_df[routes_df['route_id'] == route_id]['route_long_name'].iloc[0]

            route_scores.append({
                'route_name': route_name,
                'trip_id': trip_id,
                'stops': len(stops),
                'avg_congestion': round(avg_congestion, 2),
                'est_delay_min': round(total_delay, 2),
                'coordinates': [(stop['lat'], stop['lon']) for stop in stops],
                'congestion_values': congestion_values,
                'etas': etas
            })

    # ✅ Save updated cache only after all routes are evaluated
    with open(CACHE_FILE, "w") as f:
        json.dump(congestion_cache, f)

    # ✅ Print summary
    print("\n🚦 Congestion Data Fetch Summary")
    print(f"→ API calls made: {api_calls}")
    print(f"→ Cache hits used: {cache_hits}")
    print(f"→ Total requests processed: {api_calls + cache_hits}")

    return sorted(route_scores, key=lambda x: x['est_delay_min'])


import datetime

def get_estimated_times(stops, base_time=None):
    base_time = base_time or datetime.datetime.now()
    times = []
    current_time = base_time
    for stop in stops:
        current_speed, free_speed = get_congestion(stop['lat'], stop['lon'])
        if current_speed and free_speed:
            delay_factor = (1 - current_speed / free_speed) * 1.5
            current_time += datetime.timedelta(minutes=delay_factor)
            times.append(current_time.strftime("%H:%M"))
        else:
            times.append("N/A")
    return times

'''# ✅ THE MAIN FUNCTION TO CALL
def compute_best_routes(source, destination):
    trip_ids = find_routes_between(source, destination)
    if not trip_ids:
        return {"error": "No routes found between stops."}
    return evaluate_routes(trip_ids)'''

# ---------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
