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
md_lines.append(f"**Anchor Point:** {home['name']} ({home['address']})  ")
md_lines.append(f"**Total Mapped Destinations:** {len(cgs)} campgrounds across 9 distinct geographic sectors  ")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## ⚡ The Camper Reservation Cheat Sheet & Direct Booking")
md_lines.append("")
md_lines.append("| System / Agency | Rolling Window | Drop Time (PT) | Key Destinations | Winning Strategy |")
md_lines.append("|---|---|---|---|---|")
md_lines.append("| **California State Parks** (*ReserveCalifornia*) | **6 Months Rolling** | **8:00:00 AM** | Steep Ravine, Mt. Tamalpais, Big Sur, Fremont Peak, Salt Point, Big Basin, Henry Coe | Set digital atomic clock; site availability opens *exactly* at 08:00:00. Have profile logged in with card on file. Sells out in < 5 seconds for top weekends. |")
md_lines.append("| **National Park Service (NPS)** (*Recreation.gov*) | **3 to 6 Months Rolling** | **7:00:00 AM** | Point Reyes Backcountry (3 mo), Kirby Cove (3 mo), Pinnacles (6 mo), Lassen (6 mo), Whiskeytown (6 mo) | Kirby Cove and Point Reyes open **3 months rolling**. Pinnacles and Lassen open **6 months rolling**. |")
md_lines.append("| **Yosemite National Park** (*Recreation.gov*) | **1 Month Blocks (5 mos ahead)** | **7:00:00 AM (15th of month)** | Upper Pines, Lower Pines, North Pines | Released on the 15th of every month at 7 AM for a 1-month booking block 4-5 months out. Camp 4 uses 1-day daily lottery. |")
md_lines.append("| **US Forest Service (USFS)** (*Recreation.gov*) | **6 Months Rolling** | **7:00:00 AM** | Kirk Creek (Big Sur), Plaskett Creek, Shasta-Trinity NF | Kirk Creek ocean bluff sites are premier. Several sites kept for walk-in FCFS. |")
md_lines.append("| **East Bay Regional Parks (EBRPD)** | **12 Weeks (84 days)** | **Midnight / Portal** | Anthony Chabot, Del Valle | Easiest reservations for spontaneous weekend getaways; very dog-friendly. |")
md_lines.append("| **Santa Clara & San Mateo County Parks** | **6 Months Rolling** | **Midnight** | Memorial Park, Sanborn, Mount Madonna, Uvas Canyon | Excellent redwood and waterfall camping; great family sites. |")
md_lines.append("| **First-Come, First-Served (FCFS)** | **Same-Day Arrival** | **Open Daily 365 Days** | Pantoll & Bootjack (Mt. Tam), Prewitt Ridge, Trinity Alps Trailheads | Open year-round. Midweek is easy; for weekend stays, arrive early Friday morning (by 8:00 AM) as weekend demand fills every site by midday. |")
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
        md_lines.append(f"- **Drive from Home:** **{c['drive_time_from_home']}** (~{c['distance_road_miles']} road miles | {c['distance_straight_miles']} mi straight-line)")
        md_lines.append(f"- **Reservation Type:** `{c['reservation_type']}`")
        md_lines.append(f"- **When Reservations Open:** {c['reservation_window']}")
        md_lines.append(f"- **Capacity & Site Types:** {c['num_sites']} sites ({c['site_types']}) | **Fee:** {c['nightly_fee']}")
        md_lines.append(f"- **Composite Rating:** **{c['composite_score_out_of_10']}/10** *(Public: {c['rating_public']}/5.0 | Hike Proximity: {c['rating_hikes']}/5.0)*")
        md_lines.append(f"- **Nearby Hikes & Natural Attractions:** {c['nearby_hikes_attractions']}")
        md_lines.append(f"- **Direct Links:** [Reserve Campsite ↗]({c['direct_booking_url']}) | [Park Overview & Hikes ↗]({c['overview_url']})")
        md_lines.append(f"- **Overview & Insider Tips:** {c['description']}")
        md_lines.append("")

guide_content = "\n".join(md_lines)

with open("CAMPGROUND_INTELLIGENCE_GUIDE.md", "w") as f:
    f.write(guide_content)

with open("/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/campground_guide.md", "w") as f:
    f.write(guide_content)

print("Updated CAMPGROUND_INTELLIGENCE_GUIDE.md with 53 campgrounds and Pantoll/Bootjack clarification!")
