#!/usr/bin/env python3
"""
update_svg_map.py
Generates a rich, cartographic static SVG vector map (norcal_campground_map.svg) with:
- 101 individually listed campgrounds with pastel agency color codes
- High-resolution park and wilderness boundary polygons (145 surveyed boundaries)
- Prominent hiking trail vector paths (PCT, JMT, TRT, iconic regional hikes)
- Prominent peaks with elevations, lakes, and landmarks with fixed crosshairs
- Clean Southwest distance rings (25, 50, 100, 200 mi) from Home
- Upper-right collapsible-style legend and title block matching the web dashboard
"""

import json
import math

with open("campgrounds_data.json", "r") as f:
    cg_data = json.load(f)

with open("park_boundaries.geojson", "r") as f:
    boundaries_data = json.load(f)

with open("prominent_trails.geojson", "r") as f:
    trails_data = json.load(f)

with open("prominent_landmarks.geojson", "r") as f:
    landmarks_data = json.load(f)

cgs = cg_data["campgrounds"]
home = cg_data["home_point"]

MIN_LAT = 36.1
MAX_LAT = 41.8
MIN_LNG = -124.6
MAX_LNG = -117.8

WIDTH = 1280
HEIGHT = 1040

def project(lat, lng):
    x = (lng - MIN_LNG) / (MAX_LNG - MIN_LNG) * WIDTH
    y = (MAX_LAT - lat) / (MAX_LAT - MIN_LAT) * HEIGHT
    return round(x, 1), round(y, 1)

home_x, home_y = project(home["lat"], home["lng"])

def get_agency_color(agency, name=""):
    if "National Park" in agency or "NPS" in agency:
        return "#7dd3fc"  # Powder Blue
    elif "State Park" in agency or "State Rec" in agency or "Nevada State" in agency or "State Beach" in agency:
        return "#6ee7b7"  # Pastel Mint
    elif "Wilderness" in agency or "Wilderness" in name:
        return "#d8b4fe"  # Pastel Lilac
    elif "Forest" in agency or "USFS" in agency:
        return "#bef264"  # Pastel Sage
    elif "BLM" in agency or "Reclamation" in agency or "Corps" in agency:
        return "#fde047"  # Pastel Buttercup
    else:
        return "#f472b6"  # Pastel Rose

svg_lines = []
svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" height="auto" style="background:#090d16; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">')

# Background
svg_lines.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#090d16"/>')

# Stylized Pacific Ocean polygon (approximate California coastline shelf)
svg_lines.append('<path d="M 0,0 L 235,0 L 240,130 L 255,250 L 280,360 L 295,420 L 320,470 L 350,570 L 390,660 L 440,760 L 515,860 L 610,1040 L 0,1040 Z" fill="#0b1727" opacity="0.7"/>')

# Clean Distance Rings with Southwest labels (no arrows, no boxes, no borders)
for radius_mi in [25, 50, 100, 200]:
    r_px = round((radius_mi / ((MAX_LAT - MIN_LAT) * 69.0)) * HEIGHT * 1.02, 1)
    svg_lines.append(f'<circle cx="{home_x}" cy="{home_y}" r="{r_px}" fill="none" stroke="#475569" stroke-width="1.1" stroke-dasharray="4,5" opacity="0.45"/>')
    
    label_x = round(home_x - (r_px * 0.7071) - 4, 1)
    label_y = round(home_y + (r_px * 0.7071) + 4, 1)
    
    svg_lines.append(f'<text x="{label_x}" y="{label_y}" fill="#94a3b8" font-size="11" font-weight="500" text-anchor="middle">{radius_mi} mi</text>')

# 1. High-Resolution Park & Wilderness Boundary Polygons (with zoom-out friendly pastel palette)
svg_lines.append('<g id="park-boundaries">')
for feat in boundaries_data.get("features", []):
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    layer = props.get("layer", "parks")
    cat = props.get("category", "")
    
    if layer == "forests":
        color = "#bef264"
        fill_col = "#bef264"
        fill_op = 0.04
        stroke_w = 0.8
        stroke_op = 0.35
        dash = ""
    elif "Wilderness" in cat:
        color = "#d8b4fe"
        fill_col = "#d8b4fe"
        fill_op = 0.12
        stroke_w = 1.0
        stroke_op = 0.60
        dash = ""  # Clean hairline on overview map to prevent distracting visual strobing
    elif "National Park" in cat or "Recreation Area" in cat or "National Monument" in cat:
        if "Scenic" in cat or "BLM" in props.get("agency", ""):
            color = "#fde047"
            fill_col = "#fde047"
        else:
            color = "#7dd3fc"
            fill_col = "#7dd3fc"
        fill_op = 0.16
        stroke_w = 1.2
        stroke_op = 0.85
        dash = ""
    elif "Regional" in cat or "County" in cat:
        color = "#f472b6"
        fill_col = "#f472b6"
        fill_op = 0.16
        stroke_w = 1.2
        stroke_op = 0.85
        dash = ""
    else:
        # State Parks / Beaches / Reserves
        color = "#6ee7b7"
        fill_col = "#6ee7b7"
        fill_op = 0.16
        stroke_w = 1.2
        stroke_op = 0.85
        dash = ""
    
    def ring_to_path(ring):
        pts = [project(pt[1], pt[0]) for pt in ring]
        return "M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z"
    
    d_str = ""
    if geom.get("type") == "Polygon":
        d_str = " ".join(ring_to_path(ring) for ring in geom.get("coordinates", []))
    elif geom.get("type") == "MultiPolygon":
        d_str = " ".join(ring_to_path(ring) for poly in geom.get("coordinates", []) for ring in poly)
        
    if d_str:
        svg_lines.append(f'<path d="{d_str}" fill="{fill_col}" fill-opacity="{fill_op}" stroke="{color}" stroke-opacity="{stroke_op}" stroke-width="{stroke_w}" {dash}/>')
svg_lines.append('</g>')

# 2. Prominent Hiking Trails Vector Paths
svg_lines.append('<g id="hiking-trails">')
# Sort so signature trails (PCT, JMT, TRT) draw cleanly on top
def trail_sort_key(f):
    tt = f.get("properties", {}).get("trail_type", "hike")
    return {"hike": 0, "pct": 1, "trt": 2, "jmt": 3}.get(tt, 0)

sorted_trails = sorted(trails_data.get("features", []), key=trail_sort_key)

for feat in sorted_trails:
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    tt = props.get("trail_type", "hike")
    
    if tt == "pct":
        color = "#facc15"
        width = 3.6
        dash = ""
        casing = True
    elif tt == "jmt":
        color = "#22d3ee"
        width = 3.0
        dash = 'stroke-dasharray="7,5"'
        casing = True
    elif tt == "trt":
        color = "#f8fafc"
        width = 3.0
        dash = ""
        casing = True
    else:
        color = "#f97316"
        width = 2.0
        dash = ""
        casing = False
    
    def line_to_path(coords):
        pts = [project(pt[1], pt[0]) for pt in coords]
        return "M " + " L ".join(f"{x},{y}" for x, y in pts)
    
    d_str = ""
    if geom.get("type") == "LineString":
        d_str = line_to_path(geom.get("coordinates", []))
    elif geom.get("type") == "MultiLineString":
        d_str = " ".join(line_to_path(line) for line in geom.get("coordinates", []))
        
    if d_str:
        if casing:
            svg_lines.append(f'<path d="{d_str}" fill="none" stroke="#0f172a" stroke-width="{width + 2.5}" stroke-linecap="round" opacity="0.7"/>')
        svg_lines.append(f'<path d="{d_str}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" opacity="0.95" {dash}/>')
svg_lines.append('</g>')

# 3. Prominent Landmarks (Fixed cross-hairs for peaks and lakes, labels pinned)
svg_lines.append('<g id="landmarks">')
for feat in landmarks_data.get("features", []):
    props = feat.get("properties", {})
    lng, lat = feat.get("geometry", {}).get("coordinates", [0, 0])
    lx, ly = project(lat, lng)
    ltype = props.get("type", "peak")
    name = props.get("name", "")[:22]
    
    if ltype == "peak":
        svg_lines.append(f'<g transform="translate({lx},{ly})">')
        # Reticle / Crosshair
        svg_lines.append('<circle r="3.2" fill="none" stroke="#fb7185" stroke-width="1.2"/>')
        svg_lines.append('<line x1="-5.5" y1="0" x2="5.5" y2="0" stroke="#fb7185" stroke-width="1.2"/>')
        svg_lines.append('<line x1="0" y1="-5.5" x2="0" y2="5.5" stroke="#fb7185" stroke-width="1.2"/>')
        elev = props.get("elevation_ft", "")
        elev_str = f" ({elev}')" if elev else ""
        svg_lines.append(f'<text x="8" y="3" fill="#fda4af" font-size="8.5" font-weight="600">{name}<tspan fill="#94a3b8" font-size="7.5">{elev_str}</tspan></text>')
        svg_lines.append('</g>')
    elif ltype == "lake":
        svg_lines.append(f'<g transform="translate({lx},{ly})">')
        # Reticle / Crosshair
        svg_lines.append('<circle r="3.2" fill="none" stroke="#38bdf8" stroke-width="1.2"/>')
        svg_lines.append('<line x1="-5.5" y1="0" x2="5.5" y2="0" stroke="#38bdf8" stroke-width="1.2"/>')
        svg_lines.append('<line x1="0" y1="-5.5" x2="0" y2="5.5" stroke="#38bdf8" stroke-width="1.2"/>')
        svg_lines.append(f'<text x="8" y="3" fill="#7dd3fc" font-size="8.5" font-weight="600">{name}</text>')
        svg_lines.append('</g>')
svg_lines.append('</g>')

# 4. Campground Markers (Pastel colored dots with dark ring)
svg_lines.append('<g id="campgrounds">')
for c in cgs:
    cx, cy = project(c["lat"], c["lng"])
    col = get_agency_color(c["agency"], c["name"])
    
    svg_lines.append(f'<g>')
    svg_lines.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{col}" stroke="#0f172a" stroke-width="1.2"/>')
    
    offset_x = 7
    offset_y = 3
    if cx > WIDTH - 220:
        offset_x = -130
    if cy > HEIGHT - 30:
        offset_y = -6
        
    svg_lines.append(f'<text x="{cx + offset_x}" y="{cy + offset_y}" fill="#e2e8f0" font-size="8" font-weight="500">{c["name"][:18]}</text>')
    svg_lines.append('</g>')
svg_lines.append('</g>')

# 5. Home Marker
svg_lines.append(f'<g transform="translate({home_x}, {home_y})">')
svg_lines.append('<circle r="14" fill="none" stroke="#f43f5e" stroke-width="1.5" opacity="0.6"/>')
svg_lines.append('<circle r="6" fill="#f43f5e" stroke="#ffffff" stroke-width="2"/>')
svg_lines.append('<text x="10" y="4" fill="#f43f5e" font-size="12" font-weight="bold">Home</text>')
svg_lines.append('</g>')

# 6. Header Title Block
svg_lines.append(f'<text x="40" y="45" fill="#f8fafc" font-size="22" font-weight="bold">California Campgrounds, Peaks &amp; Trails Intelligence Map</text>')
svg_lines.append(f'<text x="40" y="68" fill="#94a3b8" font-size="12.5">101 Campsites • 145 Hi-Res Boundaries • 106 Hiking Paths • 75 Peaks &amp; Lakes • Anchored from Home (SF)</text>')

# 7. Map Legend in UPPER RIGHT
svg_lines.append(f'<g transform="translate({WIDTH - 300}, 25)">')
svg_lines.append('<rect width="275" height="275" rx="10" fill="#0f172a" fill-opacity="0.95" stroke="#334155" stroke-width="1"/>')
svg_lines.append('<text x="14" y="22" fill="#ffffff" font-size="12" font-weight="bold">Map Legend &amp; Overlays</text>')

# Home
svg_lines.append('<circle cx="22" cy="40" r="5" fill="#f43f5e" stroke="#fff" stroke-width="1.5"/><text x="36" y="44" fill="#e2e8f0" font-size="10.5">Home (SF Anchor)</text>')

# Trails
svg_lines.append('<line x1="14" y1="58" x2="30" y2="58" stroke="#facc15" stroke-width="3"/><text x="36" y="62" fill="#fde047" font-size="10.5">Pacific Crest Trail (PCT)</text>')
svg_lines.append('<line x1="14" y1="76" x2="30" y2="76" stroke="#22d3ee" stroke-width="2.5" stroke-dasharray="5,4"/><text x="36" y="80" fill="#67e8f9" font-size="10.5">John Muir Trail (JMT)</text>')
svg_lines.append('<line x1="14" y1="94" x2="30" y2="94" stroke="#f97316" stroke-width="2"/><text x="36" y="98" fill="#fb923c" font-size="10.5">Iconic Hiking Trails</text>')

# Crosshair Landmarks
svg_lines.append('<circle cx="22" cy="114" r="3" fill="none" stroke="#fb7185" stroke-width="1.2"/><line x1="17" y1="114" x2="27" y2="114" stroke="#fb7185"/><line x1="22" y1="109" x2="22" y2="119" stroke="#fb7185"/><text x="36" y="118" fill="#fda4af" font-size="10.5">Prominent Peaks (Crosshair)</text>')
svg_lines.append('<circle cx="22" cy="132" r="3" fill="none" stroke="#38bdf8" stroke-width="1.2"/><line x1="17" y1="132" x2="27" y2="132" stroke="#38bdf8"/><line x1="22" y1="127" x2="22" y2="137" stroke="#38bdf8"/><text x="36" y="136" fill="#7dd3fc" font-size="10.5">Alpine Lakes (Crosshair)</text>')

# Pastel Boundaries & Campsites
svg_lines.append('<line x1="14" y1="148" x2="260" y2="148" stroke="#334155" stroke-width="0.8"/>')
svg_lines.append('<text x="14" y="162" fill="#94a3b8" font-size="9" font-weight="600" letter-spacing="0.5">BOUNDARIES &amp; CAMPSITES (PASTEL)</text>')

svg_lines.append('<circle cx="22" cy="178" r="4.5" fill="#6ee7b7" stroke="#0f172a"/><text x="36" y="182" fill="#e2e8f0" font-size="10.5">State Parks (Pastel Mint)</text>')
svg_lines.append('<circle cx="22" cy="196" r="4.5" fill="#7dd3fc" stroke="#0f172a"/><text x="36" y="200" fill="#e2e8f0" font-size="10.5">National Parks / NRA (Powder Blue)</text>')
svg_lines.append('<circle cx="22" cy="214" r="4.5" fill="#d8b4fe" stroke="#0f172a"/><text x="36" y="218" fill="#e2e8f0" font-size="10.5">Wilderness Areas (Pastel Lilac)</text>')
svg_lines.append('<circle cx="22" cy="232" r="4.5" fill="#bef264" stroke="#0f172a"/><text x="36" y="236" fill="#e2e8f0" font-size="10.5">National Forests (Soft Sage)</text>')
svg_lines.append('<circle cx="22" cy="250" r="4.5" fill="#fde047" stroke="#0f172a"/><text x="36" y="254" fill="#e2e8f0" font-size="10.5">Monuments / BLM (Buttercup)</text>')
svg_lines.append('<circle cx="22" cy="268" r="4.5" fill="#f472b6" stroke="#0f172a"/><text x="36" y="272" fill="#e2e8f0" font-size="10.5">Regional &amp; County Parks (Rose)</text>')

svg_lines.append('</g>')

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)

with open("norcal_campground_map.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)

print(f"Generated norcal_campground_map.svg ({len(svg_content):,} bytes)!")
