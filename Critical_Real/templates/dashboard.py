# dashboard.py

from flask import Flask, render_template, request, jsonify
# import data_sources  <-- this line is causing the error

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('dashboard.html', map_html="<p>Map loading...</p>")

@app.route('/api/tomtom_congestion')
def tomtom_congestion():
    import requests
    lat, lon = 12.9716, 77.5946
    tomtom_key = 'YOUR_TOMTOM_API_KEY'
    url = f'https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={tomtom_key}&point={lat},{lon}'
    res = requests.get(url).json()
    level = res.get('flowSegmentData', {}).get('currentSpeed', 'N/A')
    return jsonify({'level': f"{level} km/h" if isinstance(level, (int, float)) else 'Unavailable'})

@app.route('/api/google_accidents')
def google_accidents():
    import requests
    location = '12.9716,77.5946'
    radius = 5000
    gmaps_key = 'YOUR_GOOGLE_API_KEY'
    url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius={radius}&keyword=accident&key={gmaps_key}'
    res = requests.get(url).json()
    count = len(res.get('results', []))
    return jsonify({'count': count})

if __name__ == '__main__':
    app.run(debug=True)