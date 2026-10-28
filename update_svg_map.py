import json
import math

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

cgs = data["campgrounds"]
home = data["home_point"]

MIN_LAT = 36.3
MAX_LAT = 41.7
MIN_LNG = -124.6
MAX_LNG = -117.8

WIDTH = 1180
HEIGHT = 960

def project(lat, lng):
    x = (lng - MIN_LNG) / (MAX_LNG - MIN_LNG) * WIDTH
    y = (MAX_LAT - lat) / (MAX_LAT - MIN_LAT) * HEIGHT
    return round(x, 1), round(y, 1)

home_x, home_y = project(home["lat"], home["lng"])

def get_color(agency):
    if "National Park" in agency or "NPS" in agency:
        return "#38bdf8"
    elif "State Park" in agency or "State Rec" in agency or "Nevada State" in agency:
        return "#34d399"
    elif "Forest" in agency or "BLM" in agency:
        return "#fbbf24"
    else:
        return "#c084fc"

svg_lines = []
svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" height="auto" style="background:#090d16; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">')

svg_lines.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#090d16"/>')
svg_lines.append('<path d="M 0,0 L 220,0 L 225,120 L 240,230 L 265,340 L 278,390 L 305,440 L 335,540 L 375,620 L 420,710 L 490,810 L 580,960 L 0,960 Z" fill="#0c1929" opacity="0.6"/>')

# Simple radius labels Southwest (no arrows, no boxes, no borders, no "radius")
for radius_mi in [25, 50, 100, 200]:
    r_px = round((radius_mi / ((MAX_LAT - MIN_LAT) * 69.0)) * HEIGHT * 1.02, 1)
    svg_lines.append(f'<circle cx="{home_x}" cy="{home_y}" r="{r_px}" fill="none" stroke="#475569" stroke-width="1.1" stroke-dasharray="4,5" opacity="0.45"/>')
    
    label_x = round(home_x - (r_px * 0.7071) - 4, 1)
    label_y = round(home_y + (r_px * 0.7071) + 4, 1)
    
    svg_lines.append(f'<text x="{label_x}" y="{label_y}" fill="#94a3b8" font-size="11" font-weight="500" text-anchor="middle">{radius_mi} mi</text>')

# Header Title Block
svg_lines.append(f'<text x="40" y="45" fill="#f8fafc" font-size="22" font-weight="bold">California Campgrounds & Wilderness Explorer</text>')
svg_lines.append(f'<text x="40" y="68" fill="#94a3b8" font-size="12.5">69 Destinations • Bay Area, Coast, Tahoe Basin & Eastern Sierra • Radii from Home (SF)</text>')

# Map Legend in UPPER RIGHT
svg_lines.append(f'<g transform="translate({WIDTH - 270}, 30)">')
svg_lines.append('<rect width="240" height="152" rx="10" fill="#0f172a" fill-opacity="0.95" stroke="#334155" stroke-width="1"/>')
svg_lines.append('<text x="14" y="22" fill="#ffffff" font-size="12" font-weight="bold">Map Legend</text>')
svg_lines.append('<circle cx="24" cy="44" r="6" fill="#f43f5e" stroke="#fff" stroke-width="1.5"/><text x="40" y="48" fill="#e2e8f0" font-size="11">Home (SF)</text>')
svg_lines.append('<circle cx="24" cy="68" r="5" fill="#34d399"/><text x="40" y="72" fill="#e2e8f0" font-size="11">California & NV State Parks</text>')
svg_lines.append('<circle cx="24" cy="92" r="5" fill="#38bdf8"/><text x="40" y="96" fill="#e2e8f0" font-size="11">National Parks / NRA (NPS)</text>')
svg_lines.append('<circle cx="24" cy="116" r="5" fill="#fbbf24"/><text x="40" y="120" fill="#e2e8f0" font-size="11">USFS / BLM / Wilderness ($0)</text>')
svg_lines.append('<circle cx="24" cy="138" r="5" fill="#c084fc"/><text x="40" y="142" fill="#e2e8f0" font-size="11">Regional & County Parks</text>')
svg_lines.append('</g>')

# Home Marker
svg_lines.append(f'<g transform="translate({home_x}, {home_y})">')
svg_lines.append('<circle r="14" fill="none" stroke="#f43f5e" stroke-width="1.5" opacity="0.6"/>')
svg_lines.append('<circle r="6.5" fill="#f43f5e" stroke="#ffffff" stroke-width="2"/>')
svg_lines.append('<text x="12" y="4" fill="#f43f5e" font-size="12" font-weight="bold">Home</text>')
svg_lines.append('</g>')

# Campground Points
for c in cgs:
    cx, cy = project(c["lat"], c["lng"])
    col = get_color(c["agency"])
    
    svg_lines.append(f'<g>')
    svg_lines.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{col}" stroke="#0f172a" stroke-width="1"/>')
    
    offset_x = 7
    offset_y = 3.5
    if cx > WIDTH - 190:
        offset_x = -135
    if cy > HEIGHT - 30:
        offset_y = -8
        
    svg_lines.append(f'<text x="{cx + offset_x}" y="{cy + offset_y}" fill="#e2e8f0" font-size="9" font-weight="500">{c["name"][:20]} <tspan fill="#38bdf8" font-size="8">({c["drive_time_from_home"]})</tspan></text>')
    svg_lines.append('</g>')

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)

with open("norcal_campground_map.svg", "w") as f:
    f.write(svg_content)

with open("/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/norcal_campground_map.svg", "w") as f:
    f.write(svg_content)

print("Updated norcal_campground_map.svg with expanded Sierra extent and 69 destinations!")
