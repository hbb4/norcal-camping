import json

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

cgs = data["campgrounds"]
home = data["home_point"]

MIN_LAT = 35.4
MAX_LAT = 41.6
MIN_LNG = -124.4
MAX_LNG = -119.0

WIDTH = 1100
HEIGHT = 900

def project(lat, lng):
    x = (lng - MIN_LNG) / (MAX_LNG - MIN_LNG) * WIDTH
    y = (MAX_LAT - lat) / (MAX_LAT - MIN_LAT) * HEIGHT
    return round(x, 1), round(y, 1)

home_x, home_y = project(home["lat"], home["lng"])

def get_color(agency):
    if "National Park" in agency or "NPS" in agency:
        return "#0284c7" # Sky blue
    elif "State Park" in agency:
        return "#10b981" # Emerald green
    elif "Forest" in agency or "BLM" in agency:
        return "#f59e0b" # Amber
    else:
        return "#8b5cf6" # Purple

svg_lines = []
svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" height="auto" style="background:#0f172a; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">')

# Title & Metadata
svg_lines.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#0f172a"/>')

# Pacific Ocean stylized block
svg_lines.append('<path d="M 0,0 L 290,0 L 320,110 L 330,210 L 365,345 L 385,385 L 400,430 L 435,540 L 470,610 L 515,700 L 580,790 L 670,900 L 0,900 Z" fill="#082f49" opacity="0.4"/>')

# Distance rings
for radius_mi, label in [(25, "25 Miles"), (50, "50 Miles"), (100, "100 Miles"), (200, "200 Miles")]:
    # 1 degree lat ~ 69 miles -> scale
    r_px = round((radius_mi / ((MAX_LAT - MIN_LAT) * 69.0)) * HEIGHT * 1.05, 1)
    svg_lines.append(f'<circle cx="{home_x}" cy="{home_y}" r="{r_px}" fill="none" stroke="#475569" stroke-width="1.2" stroke-dasharray="5,5" opacity="0.6"/>')
    svg_lines.append(f'<text x="{home_x + r_px + 4}" y="{home_y - 6}" fill="#94a3b8" font-size="11" font-weight="600">{label}</text>')

# Header Block
svg_lines.append(f'<text x="40" y="50" fill="#f8fafc" font-size="24" font-weight="bold">Northern & Central California Campgrounds</text>')
svg_lines.append(f'<text x="40" y="75" fill="#94a3b8" font-size="13">Centered on Grace Cathedral (San Francisco) • NPS, CA State Parks, USFS, BLM & Regional Lands</text>')

# Legend
svg_lines.append('<g transform="translate(40, 100)">')
svg_lines.append('<rect width="260" height="150" rx="8" fill="#1e293b" opacity="0.9" stroke="#334155"/>')
svg_lines.append('<text x="15" y="24" fill="#ffffff" font-size="12" font-weight="bold">Jurisdiction Legend</text>')
svg_lines.append('<circle cx="25" cy="48" r="6" fill="#f43f5e" stroke="#fff" stroke-width="1.5"/><text x="42" y="52" fill="#e2e8f0" font-size="11">Grace Cathedral (Home Anchor)</text>')
svg_lines.append('<circle cx="25" cy="72" r="5" fill="#10b981"/><text x="42" y="76" fill="#e2e8f0" font-size="11">California State Parks</text>')
svg_lines.append('<circle cx="25" cy="96" r="5" fill="#0284c7"/><text x="42" y="100" fill="#e2e8f0" font-size="11">National Parks / NRA (NPS)</text>')
svg_lines.append('<circle cx="25" cy="120" r="5" fill="#f59e0b"/><text x="42" y="124" fill="#e2e8f0" font-size="11">USFS / BLM / Free Dispersed</text>')
svg_lines.append('<circle cx="25" cy="140" r="5" fill="#8b5cf6"/><text x="42" y="144" fill="#e2e8f0" font-size="11">Regional / County Parks</text>')
svg_lines.append('</g>')

# Grace Cathedral Marker
svg_lines.append(f'<g transform="translate({home_x}, {home_y})">')
svg_lines.append('<circle r="14" fill="none" stroke="#f43f5e" stroke-width="2" opacity="0.7"/>')
svg_lines.append('<circle r="7" fill="#f43f5e" stroke="#ffffff" stroke-width="2"/>')
svg_lines.append('<text x="14" y="5" fill="#f43f5e" font-size="13" font-weight="bold">Grace Cathedral</text>')
svg_lines.append('</g>')

# Campground Points
for c in cgs:
    cx, cy = project(c["lat"], c["lng"])
    col = get_color(c["agency"])
    score = c["composite_score_out_of_10"]
    rule = "FCFS" if "First-Come" in c["reservation_type"] else ("Dispersed" if "Dispersed" in c["reservation_type"] else "Res")
    
    svg_lines.append(f'<g>')
    svg_lines.append(f'<circle cx="{cx}" cy="{cy}" r="6.5" fill="{col}" stroke="#ffffff" stroke-width="1.2"/>')
    # Label with smart offset
    offset_x = 9
    offset_y = 4
    if cx > 800:
        offset_x = -130
    if cy > 820:
        offset_y = -10
    svg_lines.append(f'<text x="{cx + offset_x}" y="{cy + offset_y}" fill="#f1f5f9" font-size="10.5" font-weight="500">{c["name"][:24]} <tspan fill="#38bdf8" font-size="9">({c["drive_time_from_grace"]})</tspan></text>')
    svg_lines.append('</g>')

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)

with open("norcal_campground_map.svg", "w") as f:
    f.write(svg_content)

with open("/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/norcal_campground_map.svg", "w") as f:
    f.write(svg_content)

print("Generated norcal_campground_map.svg in workspace and artifact directory!")
