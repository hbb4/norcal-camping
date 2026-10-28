import json

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

cgs = data["campgrounds"]
home = data["home_point"]

# Group by region
regions = {}
for c in cgs:
    reg = c["region"]
    if reg not in regions:
        regions[reg] = []
    regions[reg].append(c)

md_lines = []
md_lines.append("# Northern California & Bay Area Campground Intelligence Guide")
md_lines.append(f"**Anchor Point:** Grace Cathedral (1100 California St, San Francisco, CA 94108)  ")
md_lines.append(f"**Total Mapped Destinations:** {len(cgs)} campgrounds across 8 distinct geographic sectors  ")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## ⚡ The SF Camper Reservation Cheat Sheet")
md_lines.append("")
md_lines.append("| Agency / System | Rolling Window | Release Time | Key Destinations Covered | Tactical Advice |")
md_lines.append("|---|---|---|---|---|")
md_lines.append("| **California State Parks** (*ReserveCalifornia*) | **6 Months Rolling** | **8:00:00 AM PT** | Steep Ravine, Mt. Tamalpais, Big Sur (Pfeiffer), Salt Point, Big Basin, Half Moon Bay | Set digital atomic clock; site availability opens *exactly* at 08:00:00. Have profile logged in and card on file. Sells out in < 5 seconds for weekends. |")
md_lines.append("| **National Park Service (NPS)** (*Recreation.gov*) | **3 to 6 Months Rolling** | **7:00:00 AM PT** | Point Reyes Backcountry (3 mo), Kirby Cove (3 mo), Pinnacles (6 mo), Lassen (6 mo), Whiskeytown (6 mo) | Kirby Cove and Wildcat/Coast camps drop on 3-month rolling basis. Pinnacles & Lassen drop on 6-month rolling. |")
md_lines.append("| **Yosemite National Park** (*Recreation.gov*) | **1 Month Blocks (5 mos ahead)** | **7:00:00 AM PT (15th of month)** | Upper Pines, Lower Pines, North Pines | Released on the 15th of every month at 7 AM for a 1-month booking block 4-5 months out. Camp 4 uses 1-day daily lottery. |")
md_lines.append("| **US Forest Service (USFS)** (*Recreation.gov*) | **6 Months Rolling** | **7:00:00 AM PT** | Kirk Creek (Big Sur), Plaskett Creek, Shasta-Trinity NF | Kirk Creek ocean bluff sites are premier. Several sites kept for walk-in FCFS. |")
md_lines.append("| **East Bay Regional Parks (EBRPD)** | **12 Weeks (84 days)** | **Midnight / Portal** | Anthony Chabot, Del Valle, Sunol | Much more accessible for spontaneous weekend getaways; dog-friendly. |")
md_lines.append("| **San Mateo County Parks** | **180 Days (6 Months)** | **Midnight** | Memorial Park, Sam McDonald | Under-the-radar redwood camping; great family sites along Pescadero Creek. |")
md_lines.append("| **First-Come, First-Served (FCFS)** | **Same-Day Arrival** | **Morning of (7-9 AM)** | Pantoll & Bootjack (Mt. Tam), Prewitt Ridge, Trinity Alps Trailheads | Arrive Thursday evening or by 8:00 AM Friday. Mt. Tamalpais kiosks accept card/cash. |")
md_lines.append("| **BLM / Dispersed Wilderness** | **No Reservation ($0)** | **Anytime** | Prewitt Ridge (Big Sur), Trinity Alps Wilderness, Panoche Hills | Requires California Campfire Permit (free online test). Leave No Trace; pack in all water. |")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🗺️ Sector-by-Sector Campground Breakdown")
md_lines.append("")

for reg_name, reg_cgs in regions.items():
    md_lines.append(f"### 📍 Sector: {reg_name}")
    md_lines.append(f"*Total Campgrounds in Sector:* {len(reg_cgs)}")
    md_lines.append("")
    
    for c in reg_cgs:
        md_lines.append(f"#### **{c['name']}**")
        md_lines.append(f"- **Managing Agency:** {c['agency']}")
        md_lines.append(f"- **Drive from Grace Cathedral:** **{c['drive_time_from_grace']}** (~{c['distance_road_miles']} road miles | {c['distance_straight_miles']} mi straight-line)")
        md_lines.append(f"- **Reservation Type:** `{c['reservation_type']}`")
        md_lines.append(f"- **When Reservations Open:** {c['reservation_window']}")
        md_lines.append(f"- **Capacity & Site Types:** {c['num_sites']} sites ({c['site_types']}) | **Fee:** {c['nightly_fee']}")
        md_lines.append(f"- **Composite Rating:** **{c['composite_score_out_of_10']}/10** *(Public: {c['rating_public']}/5.0 | Hike Proximity: {c['rating_hikes']}/5.0)*")
        md_lines.append(f"- **Nearby Hikes & Natural Attractions:** {c['nearby_hikes_attractions']}")
        md_lines.append(f"- **Overview & Insider Tips:** {c['description']}")
        md_lines.append("")

guide_content = "\n".join(md_lines)

with open("CAMPGROUND_INTELLIGENCE_GUIDE.md", "w") as f:
    f.write(guide_content)

# Also write to artifact directory with proper metadata
artifact_path = "/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/campground_guide.md"
with open(artifact_path, "w") as f:
    f.write(guide_content)

print("Saved CAMPGROUND_INTELLIGENCE_GUIDE.md in workspace and artifact directory!")
