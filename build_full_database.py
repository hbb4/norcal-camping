import json
import math

HOME = {
    "name": "Home",
    "address": "Nob Hill, San Francisco, CA",
    "lat": 37.7919,
    "lng": -122.4137
}

def calc_dist(lat, lng):
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(HOME["lat"]), math.radians(lat)
    dphi = math.radians(lat - HOME["lat"])
    dlambda = math.radians(lng - HOME["lng"])
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_straight = R * c
    
    # Real road distance estimate
    # Eastern Sierra via Sonora / Tioga (summer) or Hwy 88/89 / US-395 (winter) has higher circuity factor
    if lng < -120.5 and lat < 38.0: # Eastern Sierra south
        road_dist = round(dist_straight * 1.45, 1)
        drive_mins = int(road_dist * 1.3)
    elif lng < -119.8: # Tahoe / Northern Sierra
        road_dist = round(dist_straight * 1.32, 1)
        drive_mins = int(road_dist * 1.22)
    elif dist_straight < 15:
        road_dist = round(dist_straight * 1.35, 1)
        drive_mins = int(road_dist * 3.0)  # SF urban traffic & bridges
    elif dist_straight < 40:
        road_dist = round(dist_straight * 1.32, 1)
        drive_mins = int(road_dist * 1.8)  # Marin / Peninsula winding routes
    elif dist_straight < 100:
        road_dist = round(dist_straight * 1.3, 1)
        drive_mins = int(road_dist * 1.35) # Regional freeways & highways
    else:
        road_dist = round(dist_straight * 1.25, 1)
        drive_mins = int(road_dist * 1.15) # Long haul interstates (I-5, I-80)
    
    hrs = drive_mins // 60
    mins = drive_mins % 60
    drive_time_str = f"{hrs}h {mins:02d}m" if hrs > 0 else f"{mins} mins"
    return round(dist_straight, 1), road_dist, drive_time_str

# Load existing campgrounds if present
with open("campgrounds_data.json", "r") as f:
    existing_data = json.load(f)

print(f"Loaded {len(existing_data['campgrounds'])} existing campgrounds.")
