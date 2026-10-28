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
md_lines.append("# California Campgrounds & Wilderness Intelligence Guide")
md_lines.append(f"**Anchor Point:** {home['name']} ({home['address']})  ")
md_lines.append(f"**Total Mapped Destinations:** {len(cgs)} campgrounds across 12 distinct geographic sectors  ")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🏔️ Lake Tahoe Basin: Winter vs. Summer Intelligence")
md_lines.append("")
md_lines.append("Lake Tahoe requires two completely different operational mindsets depending on the season:")
md_lines.append("")
md_lines.append("### ❄️ Winter Strategy (November – April)")
md_lines.append("- **Snow & Access:** Snowpack typically ranges from 4 to 15+ feet at lake level (6,225 ft) and up to 25 feet on passes (Donner Summit 7,200 ft, Carson Pass 8,574 ft). Caltrans **R2 chain controls** (chains required on all vehicles except 4WD/AWD with snow-tread tires on all 4 wheels) are standard during storms on I-80, US-50, and Hwy 89.")
md_lines.append("- **Official Snow Camping:** **Sugar Pine Point State Park (West Shore / Tahoma)** is the premier state park in the entire Tahoe Basin that remains open for official vehicle winter snow camping. Camp loops are plowed, restrooms are heated with hot running water, and 12+ miles of marked Nordic ski and snowshoe trails start right at your campsite.")
md_lines.append("- **Sno-Parks:** **Blackwood Canyon Sno-Park** (Kaspian area, North Shore) and **Donner Summit Sno-Park** provide plowed staging areas for winter backcountry camping, ski touring, and snowmobiling. Requires a California Sno-Park permit ($15/day or $40/season, available online or at local gear shops).")
md_lines.append("- **Ski Area Proximity:** North Lake campgrounds (Donner Memorial, William Kent, Kaspian) are 10–20 minutes from **Palisades Tahoe, Alpine Meadows, Sugar Bowl, and Northstar**.")
md_lines.append("")
md_lines.append("### ☀️ Summer Strategy (June – September)")
md_lines.append("- **Beaches & Water:** Water temperature peaks at 65–70°F in August. **Meeks Bay** offers Caribbean-turquoise water with soft white sugar sand. **Sand Harbor** features granite monolith coves. **William Kent** and **Sugar Pine Point** provide easy beach access under Jeffrey pines.")
md_lines.append("- **Hiking & Backpacking:** The **Tahoe Rim Trail (TRT)** encircles the lake (165 miles), with immediate access into **Desolation Wilderness** via Meeks Creek, Eagle Falls, and Echo Lakes.")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🌲 Sierra National Wilderness Areas & Eastern Sierra Highlights")
md_lines.append("")
md_lines.append("| Destination | Type | Key Attractions | Booking & Permits | Seasonality |")
md_lines.append("|---|---|---|---|---|")
md_lines.append("| **Desolation Wilderness** (Eldorado NF) | Glaciated Alpine Granite | Lake Aloha, Mount Tallac, Velma Lakes, Eagle Falls | Quota permits on Recreation.gov (6 mo rolling). Day hikes free self-issue. | Jul – Sep snow-free; winter extreme ski mountaineering. |")
md_lines.append("| **Mokelumne Wilderness** (Carson Pass) | Volcanic Spire & Wildflowers | Round Top (10,381 ft), Winnemucca Lake superbloom, Frog Lake | Woods Lake campground (Rec.gov); free wilderness permits at Carson Pass station. | Jul – Aug peak flowers; Nov – Apr Carson Pass Sno-Park snowshoeing. |")
md_lines.append("| **Emigrant Wilderness** (Stanislaus NF) | Granite Basin Solitude | Relief Reservoir, Kennedy Lake, Middle Fork Stanislaus River | 100% Free wilderness permits (no quota) at Summit Ranger Station on Hwy 108. | Jul – Sep; Sonora Pass (Hwy 108) closes completely Nov – May. |")
md_lines.append("| **June Lake Loop** (Inyo NF) | Glacial Horseshoe Basin | Oh! Ridge beach, Carson Peak, Ansel Adams Wilderness gateway, Parker Lake | Rec.gov (6 mo rolling). Fills fast for summer & Oct fall colors. | Jun – Aug summer beach; Oct golden aspens; Dec – Apr June Mtn skiing. |")
md_lines.append("| **Mammoth Lakes Basin** (Inyo NF) | Alpine Crest & Volcanic Wonders | Devils Postpile basalt columns, Rainbow Falls, Duck Pass, Coldwater Creek | Rec.gov (6 mo rolling). Closes mid-Oct. | Jul – Aug alpine hiking; Nov – May world-class ski resort. |")
md_lines.append("| **Convict Lake** (Inyo NF) | Metamorphic Amphitheater | Mount Morrison 4,000-ft cliff, Convict Lake loop, natural hot springs nearby | Rec.gov (6 mo rolling) + walk-ins. | Jun – Oct camping; plowed road allows winter photo day trips. |")
md_lines.append("| **Big Pine Lakes** (Inyo NF) | Turquoise Glacial Tarns | Palisade Glacier, Temple Crag (12,999 ft), Seven Turquoise Lakes | Rec.gov (6 mo rolling) + walk-ins. | Jul – Sep peak; road closed at winter gate Nov – Apr. |")
md_lines.append("| **Whitney Portal** (Inyo NF) | Contiguous US High Point Base | Mount Whitney summit trail (14,505 ft), Lone Pine Lake, Whitney Store | Rec.gov for campground; Mt. Whitney summit requires annual Feb lottery. | Jul – Sep summit window; snowbound winter mountaineering only. |")
md_lines.append("| **Alabama Hills** (BLM / Lone Pine) | Desert Rock Arches | Mobius Arch, Shark's Tooth, Movie Road, Mt. Whitney sunrise views | 100% Free Designated Dispersed Camping (No permits). Zero water/services. | **Oct – Apr is PRIME** (crisp 60°F days); Jun – Aug blistering 105°F heat. |")
md_lines.append("| **Mono Lake & Travertine Hot Springs** | Tufa Towers & Hot Springs | Ancient 1M-yr-old saline lake, natural 103°F mineral tubs, Bodie Ghost Town | Free BLM dispersed camping near Bridgeport / Travertine tubs. | May – Oct; Travertine Hot Springs open for winter snow-soaking. |")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 📊 Multi-Field Rating System Explained")
md_lines.append("")
md_lines.append("To avoid inflating scores where every park lands above 9.0, each destination is evaluated across four distinct 10-point dimensions:")
md_lines.append("1. **🥾 Hiking & Trail Access (1–10):** Direct trailhead access to premier singletrack, elevation changes, alpine wilderness connectivity, and waterfalls.")
md_lines.append("2. **🌅 Scenery & Views (1–10):** Natural grandeur, coastal drops, dramatic granite monoliths, mountain reflections, and dark skies.")
md_lines.append("3. **⛺ Comfort & Amenities (1–10):** Quality of restrooms (heated/flush vs vault), hot showers, potable water, site spacing, shade, and RV hookups.")
md_lines.append("4. **⚡ Booking Competition (1–10):** Practical difficulty of reserving a spot (10 = sells out in seconds on drop day, e.g. Steep Ravine, Upper Pines; 2–4 = walk-up FCFS or plentiful dispersed camping).")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🗺️ Sector-by-Sector Directory (69 Destinations)")
md_lines.append("")

for reg_name, reg_cgs in regions.items():
    md_lines.append(f"### 📍 Sector: {reg_name}")
    md_lines.append(f"*Total Campgrounds in Sector:* {len(reg_cgs)}")
    md_lines.append("")
    
    for c in reg_cgs:
        md_lines.append(f"#### **{c['name']}**")
        md_lines.append(f"- **Managing Agency:** {c['agency']}")
        md_lines.append(f"- **Drive from Home:** **{c['drive_time_from_home']}** (~{c['distance_road_miles']} road miles | {c['distance_straight_miles']} mi straight-line)")
        md_lines.append(f"- **Multi-Field Ratings:** 🥾 Hiking: **{c['rating_hiking']}/10** | 🌅 Views: **{c['rating_views']}/10** | ⛺ Comfort: **{c['rating_comfort']}/10** | ⚡ Competition: **{c.get('competition_badge', c.get('rating_competition', 'Moderate'))}**")
        md_lines.append(f"- **Composite Score:** **{c['composite_score_out_of_10']}/10**")
        md_lines.append(f"- **Reservation Rule:** `{c['reservation_type']}`")
        md_lines.append(f"- **Booking Window:** {c['reservation_window']}")
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

with open("/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/campground_guide.md", "w") as f:
    f.write(guide_content)

print("Updated CAMPGROUND_INTELLIGENCE_GUIDE.md with 69 destinations and Tahoe/Sierra features!")
