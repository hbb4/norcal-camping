import json

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

with open("park_boundaries.geojson", "r") as f:
    boundaries_data = json.load(f)

with open("prominent_trails.geojson", "r") as f:
    trails_data = json.load(f)

with open("prominent_landmarks.geojson", "r") as f:
    landmarks_data = json.load(f)

cgs = data["campgrounds"]
home = data["home_point"]

# Group campgrounds by region
regions = {}
for c in cgs:
    reg = c["region"]
    if reg not in regions:
        regions[reg] = []
    regions[reg].append(c)

md_lines = []
md_lines.append("# California Campgrounds, Parks, Trails & Peaks Intelligence Guide")
md_lines.append(f"**Anchor Point:** {home['name']} ({home['address']})  ")
md_lines.append(f"**Total Individual Campsites:** {len(cgs)} individually listed campgrounds  ")
md_lines.append(f"**High-Resolution Boundaries:** 50 surveyed park & wilderness areas (174,000+ vector points)  ")
md_lines.append(f"**Prominent Hiking Trails:** 21 iconic high-resolution trail routes  ")
md_lines.append(f"**Prominent Geographic Landmarks:** 45 peaks (with elevations), alpine lakes, and major rivers  ")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🏔️ Prominent Peaks, Alpine Lakes & Major Rivers")
md_lines.append("")
md_lines.append("### ⛰️ Prominent Mountain Peaks (Ranked by Elevation)")
md_lines.append("| Peak Name | Elevation | Region / Range | Key Highlights |")
md_lines.append("|---|---|---|---|")

peaks = [lm for lm in landmarks_data["features"] if lm["properties"]["type"] == "peak"]
peaks.sort(key=lambda x: x["properties"].get("elevation_ft", 0), reverse=True)
for p in peaks:
    props = p["properties"]
    md_lines.append(f"| **{props['name']}** | **{props['elevation_ft']:,} ft** | {props.get('region', 'California')} | {props['description']} |")

md_lines.append("")
md_lines.append("### 💧 Prominent Alpine & Natural Lakes")
md_lines.append("| Lake Name | Surface Elevation | Type / Features | Highlights & Recreation |")
md_lines.append("|---|---|---|---|")
lakes = [lm for lm in landmarks_data["features"] if lm["properties"]["type"] == "lake"]
for l in lakes:
    props = l["properties"]
    elev = f"{props['elevation_ft']:,} ft" if props.get('elevation_ft') else "Sea level"
    md_lines.append(f"| **{props['name']}** | {elev} | Alpine / Reservoir | {props['description']} |")

md_lines.append("")
md_lines.append("### 🌊 Prominent Major Rivers & Waterways")
md_lines.append("| River / Creek | Watershed / Location | Key Features & Campsite Connections |")
md_lines.append("|---|---|---|")
rivers = [lm for lm in landmarks_data["features"] if lm["properties"]["type"] == "river"]
for r in rivers:
    props = r["properties"]
    md_lines.append(f"| **{props['name']}** | California Watershed | {props['description']} |")

md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🥾 Prominent Hiking Trails Directory")
md_lines.append("")
md_lines.append("| Trail Name | Park / Area | Distance & Gain | Difficulty | Trailhead Campground | Highlights |")
md_lines.append("|---|---|---|---|---|---|")
for t in trails_data["features"]:
    props = t["properties"]
    md_lines.append(f"| **{props['name']}** | {props['park_name']} | {props['distance_miles']} (↑{props['elevation_gain_ft']}) | `{props['difficulty']}` | **{props['trailhead_campground']}** | {props['description']} |")

md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🌲 Surveyed High-Resolution Park & Wilderness Boundaries (50 Areas)")
md_lines.append("")
md_lines.append("| Area Name | Category | Managing Agency | Official Acreage | Key Features |")
md_lines.append("|---|---|---|---|---|")
for b in boundaries_data["features"]:
    props = b["properties"]
    acres = f"{props['acres']:,} acres" if props.get('acres') else "N/A"
    md_lines.append(f"| **{props['name']}** | {props['category']} | {props['agency']} | {acres} | {props['description']} |")

md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🏕️ Complete Individual Campground Directory (101 Campsites)")
md_lines.append("")

for reg_name, reg_cgs in regions.items():
    md_lines.append(f"### 📍 Region: {reg_name} ({len(reg_cgs)} Campsites)")
    md_lines.append("")
    for c in reg_cgs:
        md_lines.append(f"#### **{c['name']}**")
        md_lines.append(f"- **Parent Park / Area:** `{c.get('park_name', 'California Outdoors')}`")
        md_lines.append(f"- **Managing Agency:** {c['agency']}")
        md_lines.append(f"- **Drive from Home:** **{c['drive_time_from_home']}** (~{c['distance_road_miles']} road miles | {c['distance_straight_miles']} mi straight-line)")
        md_lines.append(f"- **Multi-Field Ratings:** 🥾 Hiking: **{c['rating_hiking']}/10** | 🌅 Views: **{c['rating_views']}/10** | ⛺ Comfort: **{c['rating_comfort']}/10** | ⚡ Competition: **{c.get('competition_badge', c.get('rating_competition', 'Moderate'))}**")
        md_lines.append(f"- **Composite Score:** **{c['composite_score_out_of_10']}/10**")
        md_lines.append(f"- **Reservation Rule:** `{c['reservation_type']}`")
        md_lines.append(f"- **Booking Window:** {c['reservation_window']}")
        md_lines.append(f"- **Capacity:** {c['num_sites']} sites ({c['site_types']})")
        md_lines.append(f"- **Nightly Fee:** {c['nightly_fee']}")
        md_lines.append(f"- **Seasonal Timing:** ☀️ Peak: **{c.get('peak_season', 'Summer')}** | 🍂 Light: **{c.get('light_season', 'Winter')}**")
        if c.get("winter_profile"):
            md_lines.append(f"- **❄️ Winter & Snow Profile:** {c['winter_profile']}")
        md_lines.append(f"- **Nearby Hikes & Attractions:** {c['nearby_hikes_attractions']}")
        md_lines.append(f"- **Direct Links:** [Reserve Campsite ↗]({c['direct_booking_url']}) | [Park Overview & Hikes ↗]({c['overview_url']})")
        md_lines.append(f"- **Overview & Strategy:** {c['description']}")
        md_lines.append("")

guide_content = "\n".join(md_lines)

with open("CAMPGROUND_INTELLIGENCE_GUIDE.md", "w") as f:
    f.write(guide_content)


print(f"Generated CAMPGROUND_INTELLIGENCE_GUIDE.md ({len(guide_content):,} bytes)!")
