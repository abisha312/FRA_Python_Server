from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import math

app = Flask(__name__)
CORS(app)

# --- Define File Paths ---
VILLAGE_FILES = {
    "centroids_mp.geojson": "Madhya Pradesh",
    "villages_od.geojson": "Odisha",
    "villages_tl.geojson": "Telangana",
    "villages_tp.geojson": "Tripura"
}
WATER_FILES = {
    "fixed_waterbodies.geojson": "Madhya Pradesh",
    "fixed_waterbodies_od.geojson": "Odisha",
    "fixed_waterbodies_tl.geojson": "Telangana",
    "fixed_waterbodies_tp.geojson": "Tripura"
}

# --- Data Storage ---
fra_data = {}
water_body_locations = []

# --- Helper Functions for Geospatial Calculations ---
def find_polygon_centroid(coords):
    lon_sum = 0
    lat_sum = 0
    num_points = 0
    
    # Handle MultiPolygon format (list of lists of lists)
    if isinstance(coords[0][0][0], list):
        for part in coords:
            for ring in part:
                for lon, lat in ring:
                    lon_sum += lon
                    lat_sum += lat
                    num_points += 1
    # Handle single Polygon format (list of lists)
    else:
        for ring in coords:
            for lon, lat in ring:
                lon_sum += lon
                lat_sum += lat
                num_points += 1
    
    if num_points > 0:
        return lon_sum / num_points, lat_sum / num_points
    return None, None

def haversine(lon1, lat1, lon2, lat2):
    R = 6371  # Earth radius in kilometers
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- Data Loading Function ---
def load_data():
    global fra_data, water_body_locations
    
    # Load village data
    for file_path, state_name in VILLAGE_FILES.items():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feature in data["features"]:
                    name = feature["properties"].get("name")
                    if name and feature["geometry"] and feature["geometry"]["coordinates"]:
                        lon, lat = feature["geometry"]["coordinates"]
                        fra_data[name] = {
                            "village": name,
                            "state": state_name,
                            "lon": lon,
                            "lat": lat
                        }
        except FileNotFoundError:
            print(f"Warning: Village file not found at {file_path}")

    # Load water body data and find centroids
    for file_path, state_name in WATER_FILES.items():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feature in data["features"]:
                    if feature["geometry"] and feature["geometry"]["coordinates"]:
                        lon, lat = find_polygon_centroid(feature["geometry"]["coordinates"])
                        if lon is not None:
                            water_body_locations.append({"lon": lon, "lat": lat})
        except FileNotFoundError:
            print(f"Warning: Water body file not found at {file_path}")

# Load all data on application startup
load_data()

# --- Helper to get nearest water distance ---
def get_nearest_water_distance(lon, lat):
    min_distance = float('inf')
    for water_body in water_body_locations:
        dist = haversine(lon, lat, water_body["lon"], water_body["lat"])
        if dist < min_distance:
            min_distance = dist
    return min_distance

# --- Recommendation logic focused on water resources for Jal Jeevan authorities ---
def generate_water_recommendation(village_name):
    village_info = fra_data.get(village_name)
    if not village_info:
        return "Data not available for this village. Recommend field survey. 🌱", "N/A"

    lon, lat = village_info["lon"], village_info["lat"]
    water_dist = get_nearest_water_distance(lon, lat)

    if math.isinf(water_dist) or water_dist > 1000:
        recommendation = (
            "No water source nearby. Nearest water body is over 1000 km away. ⚠️\n"
            "Urgent intervention needed to establish sustainable water supply. "
            "Recommend Jal Jeevan Mission priority for infrastructure development."
        )
    elif water_dist > 100:
        recommendation = (
            f"No water source nearby. Nearest water body is {water_dist:.2f} km away. ⚠️\n"
            "Consider water harvesting and supply schemes under Jal Jeevan Mission."
        )
    elif water_dist > 10:
        recommendation = (
            f"Water source nearby but at {water_dist:.2f} km distance. 💧\n"
            "Recommend improving water access infrastructure and monitoring water quality."
        )
    else:
        recommendation = (
            f"Water source very close at {water_dist:.2f} km. 💧\n"
            "Focus on maintenance of existing water resources and community water management."
        )

    return recommendation, water_dist

# --- API Endpoint ---
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        input_data = request.get_json()
        results = []

        for rec in input_data.get("villages", []):
            name = rec.get("name")
            recommendation, distance_to_water = generate_water_recommendation(name)

            results.append({
                "village": name,
                "recommendation": recommendation,
                "distance_to_water": distance_to_water
            })

        return jsonify({"status": "success", "results": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    print("--- Starting Flask server ---")
    app.run(debug=True, port=5000)
