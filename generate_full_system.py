import json
import math

HOME = {
    "name": "Home",
    "address": "Nob Hill, San Francisco, CA",
    "lat": 37.7919,
    "lng": -122.4137
}

def calc_dist(lat, lng):
    R = 3958.8
    phi1, phi2 = math.radians(HOME["lat"]), math.radians(lat)
    dphi = math.radians(lat - HOME["lat"])
    dlambda = math.radians(lng - HOME["lng"])
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_straight = R * c
    
    if lng > -119.5 and lat < 38.2:
        road_dist = round(dist_straight * 1.48, 1)
        drive_mins = int(road_dist * 1.25)
    elif lng > -120.3:
        road_dist = round(dist_straight * 1.32, 1)
        drive_mins = int(road_dist * 1.22)
    elif dist_straight < 15:
        road_dist = round(dist_straight * 1.35, 1)
        drive_mins = int(road_dist * 3.0)
    elif dist_straight < 40:
        road_dist = round(dist_straight * 1.32, 1)
        drive_mins = int(road_dist * 1.8)
    elif dist_straight < 100:
        road_dist = round(dist_straight * 1.3, 1)
        drive_mins = int(road_dist * 1.35)
    else:
        road_dist = round(dist_straight * 1.25, 1)
        drive_mins = int(road_dist * 1.15)
    
    hrs = drive_mins // 60
    mins = drive_mins % 60
    drive_time_str = f"{hrs}h {mins:02d}m" if hrs > 0 else f"{mins} mins"
    return round(dist_straight, 1), road_dist, drive_time_str

def make_cg(
    id, name, park_name, region, agency, lat, lng,
    res_type, res_window, direct_url, overview_url,
    num_sites, site_types, fee,
    hiking, views, comfort, comp,
    peak, light, winter, desc, hikes=""
):
    dist_s, dist_r, drive_time = calc_dist(lat, lng)
    comp_badge = (
        "Extreme (9-10/10)" if comp >= 9 else
        "High (7-8/10)" if comp >= 7 else
        "Moderate (5-6/10)" if comp >= 5 else
        "Accessible (2-4/10)"
    )
    composite = round((hiking * 0.35) + (views * 0.35) + (comfort * 0.30), 1)
    return {
        "id": id,
        "name": name,
        "park_name": park_name,
        "region": region,
        "agency": agency,
        "lat": lat,
        "lng": lng,
        "distance_straight_miles": dist_s,
        "distance_road_miles": dist_r,
        "drive_time_from_home": drive_time,
        "reservation_type": res_type,
        "reservation_window": res_window,
        "direct_booking_url": direct_url,
        "overview_url": overview_url,
        "num_sites": num_sites,
        "site_types": site_types,
        "nightly_fee": fee,
        "rating_hiking": float(hiking),
        "rating_views": float(views),
        "rating_comfort": float(comfort),
        "rating_competition": int(comp),
        "competition_badge": comp_badge,
        "composite_score_out_of_10": composite,
        "peak_season": peak,
        "light_season": light,
        "winter_profile": winter,
        "nearby_hikes_attractions": hikes,
        "description": desc
    }

print("Campground helper built successfully.")
