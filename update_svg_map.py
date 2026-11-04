#!/usr/bin/env python3
"""
update_svg_map.py
Generates a rich, cartographic static SVG vector map (norcal_campground_map.svg) with:
- 101 individually listed campgrounds with agency color codes
- High-resolution park and wilderness boundary polygons
- Prominent hiking trail vector paths
- Prominent peaks with elevations, prominent lakes and rivers
- Clean Southwest distance rings (25, 50, 100, 200 mi) from Home
- Upper-right collapsible-style legend and title block
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

def get_agency_color(agency):
    if "National Park" in agency or "NPS" in agency:
        return "#38bdf8"
    elif "State Park" in agency or "State Rec" in agency or "Nevada State" in agency:
        return "#34d399"
    elif "Wilderness" in agency:
        return "#c084fc"
    elif "Forest" in agency or "BLM" in agency:
        return "#fbbf24"
    else:
        return "#f472b6"

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

# 1. High-Resolution Park & Wilderness Boundary Polygons
svg_lines.append('<g id="park-boundaries" opacity="0.55">')
for feat in boundaries_data.get("features", []):
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    color = props.get("color", "#10b981")
    fill_col = props.get("fillColor", "#10b981")
    dash = 'stroke-dasharray="4,3"' if props.get("dashArray") else ''
    
    def ring_to_path(ring):
        pts = [project(pt[1], pt[0]) for pt in ring]
        return "M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z"
    
    d_str = ""
    if geom.get("type") == "Polygon":
        d_str = " ".join(ring_to_path(ring) for ring in geom.get("coordinates", []))
    elif geom.get("type") == "MultiPolygon":
        d_str = " ".join(ring_to_path(ring) for poly in geom.get("coordinates", []) for ring in poly)
        
    if d_str:
        svg_lines.append(f'<path d="{d_str}" fill="{fill_col}" fill-opacity="0.12" stroke="{color}" stroke-width="1.2" {dash}/>')
svg_lines.append('</g>')

# 2. Prominent Hiking Trails Vector Paths
svg_lines.append('<g id="hiking-trails" opacity="0.85">')
for feat in trails_data.get("features", []):
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    color = props.get("color", "#f97316")
    dash = 'stroke-dasharray="5,4"' if "National" in props.get("category", "") else ''
    
    def line_to_path(coords):
        pts = [project(pt[1], pt[0]) for pt in coords]
        return "M " + " L ".join(f"{x},{y}" for x, y in pts)
    
    d_str = ""
    if geom.get("type") == "LineString":
        d_str = line_to_path(geom.get("coordinates", []))
    elif geom.get("type") == "MultiLineString":
        d_str = " ".join(line_to_path(line) for line in geom.get("coordinates", []))
        
    if d_str:
        svg_lines.append(f'<path d="{d_str}" fill="none" stroke="{color}" stroke-width="2.2" {dash}/>')
svg_lines.append('</g>')

# 3. Prominent Landmarks (Peaks, Lakes, Rivers)
svg_lines.append('<g id="landmarks">')
for feat in landmarks_data.get("features", []):
    props = feat.get("properties", {})
    lng, lat = feat.get("geometry", {}).get("coordinates", [0, 0])
    lx, ly = project(lat, lng)
    ltype = props.get("type", "peak")
    
    if ltype == "peak":
        svg_lines.append(f'<g transform="translate({lx},{ly})">')
        svg_lines.append('<polygon points="0,-7 6,4 -6,4" fill="#f43f5e" stroke="#ffffff" stroke-width="1"/>')
        svg_lines.append(f'<text x="8" y="2" fill="#fda4af" font-size="8.5" font-weight="bold">{props.get("name")[:18]} <tspan fill="#fca5a5" font-size="7.5">({props.get("elevation_ft", "")}\')</tspan></text>')
        svg_lines.append('</g>')
    elif ltype == "lake":
        svg_lines.append(f'<g transform="translate({lx},{ly})">')
        svg_lines.append('<circle r="4" fill="#0ea5e9" stroke="#ffffff" stroke-width="1"/>')
        svg_lines.append(f'<text x="6" y="2" fill="#7dd3fc" font-size="8.5" font-weight="600">{props.get("name")[:18]}</text>')
        svg_lines.append('</g>')
    elif ltype == "river":
        svg_lines.append(f'<g transform="translate({lx},{ly})">')
        svg_lines.append('<circle r="3" fill="#06b6d4"/>')
        svg_lines.append(f'<text x="5" y="2" fill="#67e8f9" font-size="8" font-style="italic">{props.get("name")[:18]}</text>')
        svg_lines.append('</g>')
svg_lines.append('</g>')

# 4. Campground Markers
svg_lines.append('<g id="campgrounds">')
for c in cgs:
    cx, cy = project(c["lat"], c["lng"])
    col = get_agency_color(c["agency"])
    
    svg_lines.append(f'<g>')
    svg_lines.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{col}" stroke="#0f172a" stroke-width="1"/>')
    
    offset_x = 6
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
svg_lines.append(f'<text x="40" y="45" fill="#f8fafc" font-size="22" font-weight="bold">California Campgrounds, Peaks & Trails Intelligence Map</text>')
svg_lines.append(f'<text x="40" y="68" fill="#94a3b8" font-size="12.5">101 Campsites • 50 Hi-Res Park Boundaries • 21 Iconic Hiking Paths • 45 Peaks & Lakes • Anchored from Home (SF)</text>')

# 7. Map Legend in UPPER RIGHT
svg_lines.append(f'<g transform="translate({WIDTH - 290}, 30)">')
svg_lines.append('<rect width="260" height="205" rx="10" fill="#0f172a" fill-opacity="0.95" stroke="#334155" stroke-width="1"/>')
svg_lines.append('<text x="14" y="22" fill="#ffffff" font-size="12" font-weight="bold">Map Legend & Overlays</text>')
svg_lines.append('<circle cx="22" cy="42" r="5.5" fill="#f43f5e" stroke="#fff" stroke-width="1.5"/><text x="36" y="46" fill="#e2e8f0" font-size="10.5">Home (SF Anchor)</text>')
svg_lines.append('<line x1="14" y1="62" x2="30" y2="62" stroke="#f97316" stroke-width="2.5"/><text x="36" y="66" fill="#fb923c" font-size="10.5">Iconic Hiking Trails</text>')
svg_lines.append('<polygon points="22,78 27,87 17,87" fill="#f43f5e"/><text x="36" y="86" fill="#fda4af" font-size="10.5">Prominent Peaks ⛰️ (Elev. ft)</text>')
svg_lines.append('<circle cx="22" cy="104" r="4" fill="#0ea5e9"/><text x="36" y="108" fill="#7dd3fc" font-size="10.5">Alpine Lakes 💧 & Rivers 🌊</text>')
svg_lines.append('<circle cx="22" cy="126" r="4.5" fill="#34d399"/><text x="36" y="130" fill="#e2e8f0" font-size="10.5">California & NV State Parks</text>')
svg_lines.append('<circle cx="22" cy="148" r="4.5" fill="#38bdf8"/><text x="36" y="152" fill="#e2e8f0" font-size="10.5">National Parks / NRA (NPS)</text>')
svg_lines.append('<circle cx="22" cy="170" r="4.5" fill="#c084fc"/><text x="36" y="174" fill="#e2e8f0" font-size="10.5">Wilderness Areas (USFS/BLM)</text>')
svg_lines.append('<circle cx="22" cy="192" r="4.5" fill="#f472b6"/><text x="36" y="196" fill="#e2e8f0" font-size="10.5">Regional & County Parks</text>')
svg_lines.append('</g>')

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)

with open("norcal_campground_map.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)


print(f"Generated norcal_campground_map.svg ({len(svg_content):,} bytes)!")
