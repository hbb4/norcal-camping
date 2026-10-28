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
    if lng > -119.5 and lat < 38.2: # Eastern Sierra south (Mono, Mammoth, Big Pine, Lone Pine)
        road_dist = round(dist_straight * 1.48, 1)
        drive_mins = int(road_dist * 1.25)
    elif lng > -120.3: # Tahoe / Northern Sierra
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

# Load existing 53 campgrounds
with open("campgrounds_data.json", "r") as f:
    existing_file = json.load(f)
    existing_cgs = existing_file["campgrounds"]

# Existing ID lookup
cgs_dict = {c["id"]: c for c in existing_cgs}

# Helper to enrich rating fields
# Default rating profiles for existing categories if not explicitly overridden:
def enrich_ratings(cg, hiking, views, comfort, competition, peak, light, winter, summer=""):
    cg["rating_hiking"] = hiking
    cg["rating_views"] = views
    cg["rating_comfort"] = comfort
    cg["rating_competition"] = competition
    
    if competition >= 9:
        cg["competition_badge"] = "Extreme (9-10/10)"
    elif competition >= 7:
        cg["competition_badge"] = "High (7-8/10)"
    elif competition >= 5:
        cg["competition_badge"] = "Moderate (5-6/10)"
    else:
        cg["competition_badge"] = "Accessible (2-4/10)"
        
    cg["peak_season"] = peak
    cg["light_season"] = light
    cg["winter_profile"] = winter
    cg["summer_profile"] = summer if summer else cg.get("description", "")
    
    # Recalculate balanced composite score (out of 10)
    # Composite = 35% Hiking + 35% Views + 30% Comfort
    cg["composite_score_out_of_10"] = round((hiking * 0.35) + (views * 0.35) + (comfort * 0.30), 1)

# Apply ratings to key existing campgrounds to give genuine diversity
if "rob_hill" in cgs_dict:
    enrich_ratings(cgs_dict["rob_hill"], 6, 8, 8, 8, "May – Sep", "Closed Nov – Mar", 
                   "Closed for winter (open Apr–Oct only). Wet cypress coastal fog.", "Sunny SF summer days, group campfires, Baker beach strolls.")
if "kirby_cove" in cgs_dict:
    enrich_ratings(cgs_dict["kirby_cove"], 8, 10, 5, 10, "May – Oct", "Nov – Mar (Crisp & foggy)",
                   "Open year-round; chilly coastal winds, heavy fog, but stunning crisp winter sunsets framing Golden Gate Bridge.", "World's most scenic urban campsite; direct beach access.")
if "bicentennial" in cgs_dict:
    enrich_ratings(cgs_dict["bicentennial"], 8, 8, 4, 7, "Apr – Oct", "Nov – Mar", 
                   "Open year-round; cold ocean winds, vault toilets only, pack all water in.", "Headlands trail running, hawk watching, Point Bonita lighthouse.")
if "haypress_hawkcamp" in cgs_dict:
    enrich_ratings(cgs_dict["haypress_hawkcamp"], 9, 9, 3, 7, "May – Oct", "Nov – Mar",
                   "Open year-round; pack-in water, exposed ridge camping, muddy trails after winter rains.", "Backpacking getaway 25 min from downtown SF.")
if "pantoll_bootjack" in cgs_dict:
    enrich_ratings(cgs_dict["pantoll_bootjack"], 10, 8, 6, 7, "May – Oct (Fills by Friday 10 AM)", "Nov – Mar (Easy walk-in availability)",
                   "Open 365 days a year! Winter brings rushing waterfalls on Steep Ravine and Cataract trails, lush green moss, and fewer crowds.", "Direct trailhead for Dipsea Trail and Stinson Beach.")
if "steep_ravine" in cgs_dict:
    enrich_ratings(cgs_dict["steep_ravine"], 10, 10, 6, 10, "Year-Round (Sells out in <2 seconds)", "Winter storm watching (Extremely coveted)",
                   "Open year-round; wood-burning cast-iron stoves keep historic rustic cabins cozy during dramatic Pacific winter rainstorms.", "Cliffside paradise with waves crashing on Rocky Point rocks below.")
if "china_camp" in cgs_dict:
    enrich_ratings(cgs_dict["china_camp"], 7, 7, 7, 6, "May – Oct", "Nov – Mar",
                   "Open year-round; sheltered from coastal fog, mild winter temperatures along San Pablo Bay.", "Mountain bike singletrack, historic shrimp village, warm bay breezes.")
if "samuel_p_taylor" in cgs_dict:
    enrich_ratings(cgs_dict["samuel_p_taylor"], 8, 8, 8, 8, "May – Sep", "Nov – Mar (Chilly in redwood canyon)",
                   "Open year-round; winter coho salmon spawning runs in Lagunitas Creek, roaring creek, cool redwood canyon floor.", "Paved Cross Marin bike path, peaceful old-growth redwoods.")
if "pt_reyes_backcountry" in cgs_dict:
    enrich_ratings(cgs_dict["pt_reyes_backcountry"], 10, 10, 4, 9, "May – Oct", "Nov – Mar (Tule elk rut & whale migration)",
                   "Open year-round; Pacific winter storms bring thundering surf and winter gray whale migration viewing from bluffs.", "Wildcat camp next to Alamere Falls, coastal wilderness backpacking.")
if "half_moon_bay" in cgs_dict:
    enrich_ratings(cgs_dict["half_moon_bay"], 6, 8, 9, 8, "May – Oct", "Nov – Feb (Mavericks big wave season)",
                   "Open year-round; huge winter swells at nearby Mavericks, brisk coastal walks on paved bluffs, heated coin showers.", "Beachfront camping, ocean bluffs, coastal bike path.")
if "memorial_park" in cgs_dict:
    enrich_ratings(cgs_dict["memorial_park"], 8, 8, 8, 7, "May – Sep", "Nov – Mar (Quiet creekside)",
                   "Open year-round; high winter creek levels, cool damp redwood forest, very quiet.", "Pescadero Creek swimming holes, tall second-growth redwoods.")
if "big_basin" in cgs_dict:
    enrich_ratings(cgs_dict["big_basin"], 10, 9, 5, 8, "Apr – Oct", "Nov – Mar",
                   "Open year-round (rebuilding); winter rain feeds Berry Creek and Sempervirens waterfalls, vivid green redwood rebirth.", "California's oldest state park; ancient redwoods.")
if "fremont_peak" in cgs_dict:
    enrich_ratings(cgs_dict["fremont_peak"], 8, 9, 5, 5, "Apr – Oct", "Nov – Feb (Crisp winter star viewing)",
                   "Open year-round; high ridge winds and occasional light snow dustings at 3,169 ft. Incredible crystal-clear winter night skies for astronomy.", "360-degree views of Monterey Bay, dark sky observatory.")
if "henry_coe" in cgs_dict:
    enrich_ratings(cgs_dict["henry_coe"], 9, 8, 4, 3, "Mar – May (Wildflower superbloom)", "Jun – Aug (Blistering 100°F heat)",
                   "Open year-round; crisp winter backpacking, green rolling hills, cool nights, seasonal springs flow.", "Vast 87,000-acre wilderness backpacking solitude.")
if "pfeiffer_big_sur" in cgs_dict:
    enrich_ratings(cgs_dict["pfeiffer_big_sur"], 10, 10, 8, 10, "May – Oct (Sold out 6 mos ahead)", "Nov – Mar (Off-season serene Big Sur)",
                   "Open year-round; winter rains awaken Pfeiffer Falls, rushing Big Sur River, cozy campfire evenings.", "Redwoods along Big Sur River, swimming gorge, Buzzard's Roost.")
if "julia_pfeiffer_burns" in cgs_dict:
    enrich_ratings(cgs_dict["julia_pfeiffer_burns"], 9, 10, 3, 10, "Year-Round (Only 2 sites on earth!)", "Winter (Spectacular sunsets)",
                   "Open year-round; only two walk-in sites overlooking McWay Falls and turquoise Pacific cove. Sells out instantly.", "Iconic McWay Falls, sheer cliff drops.")
if "kirk_creek" in cgs_dict:
    enrich_ratings(cgs_dict["kirk_creek"], 9, 10, 5, 9, "Apr – Oct", "Nov – Mar",
                   "Open year-round; dramatic open bluff ocean views, whale watching with binoculars from your tent.", "Unobstructed cliffside ocean views, Vicente Flat wilderness trail.")
if "prewitt_ridge" in cgs_dict:
    enrich_ratings(cgs_dict["prewitt_ridge"], 8, 10, 1, 6, "May – Oct", "Nov – Apr (Mud makes road impassable)",
                   "Primitive dirt road (Nacimiento-Fergusson / Coast Ridge Rd). 4WD required, highly impassable when muddy in winter. Zero water.", "3,200 ft directly above coastal fog bank; celestial stargazing.")
if "pinnacles_np" in cgs_dict:
    enrich_ratings(cgs_dict["pinnacles_np"], 9, 9, 7, 7, "Feb – May (Spring flowers & mild temps)", "Jun – Aug (Extreme 105°F heat)",
                   "Open year-round; winter is prime season! Mild hiking weather in the 60s, lush moss in Bear Gulch Caves, active condor flights.", "High Peaks trail into volcanic spires, talus caves, condor spotting.")

# Fill defaults for any other existing campgrounds that lack multi-dimensional ratings
for c in existing_cgs:
    if "rating_hiking" not in c:
        enrich_ratings(c, round(c.get("rating_hikes", 4.5) * 1.9, 1), 
                       round(c.get("rating_public", 4.5) * 1.9, 1), 
                       7.0, 6, "May – Oct", "Nov – Apr", 
                       "Open year-round with seasonal weather variations.", c.get("nearby_hikes_attractions", ""))

# NEW CATEGORY 1: Lake Tahoe (North Lake Focus, Winter & Summer Features)
tahoe_campgrounds = [
    {
        "id": "sugar_pine_point",
        "name": "Sugar Pine Point State Park (Winter Snow Camping & Summer Beach)",
        "region": "Lake Tahoe Basin",
        "agency": "California State Parks",
        "lat": 39.0578, "lng": -120.1242,
        "reservation_type": "Paid Reservation (Year-Round)",
        "reservation_window": "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "direct_booking_url": "https://www.reservecalifornia.com/Web/#!park/678",
        "overview_url": "https://www.parks.ca.gov/?page_id=510",
        "num_sites": 175,
        "site_types": "Drive-in tent & RV sites (Plowed loops in winter with heated restrooms!)",
        "nightly_fee": "$35",
        "rating_hiking": 9.5,
        "rating_views": 9.5,
        "rating_comfort": 9.0,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (Summer lake) & Jan – Feb (Winter snow camping)",
        "light_season": "Apr – May & Oct – Nov (Quiet shoulder seasons)",
        "winter_profile": "THE WINTER CROWN JEWEL: One of the only campgrounds in Lake Tahoe that stays open all winter for official plowed snow camping! Features heated modern restrooms with flush toilets and hot running water. Directly adjacent to 12+ miles of marked/groomed cross-country ski and snowshoe trails along General Creek (site of the 1960 Winter Olympic Nordic events). Snowpack often 4 to 8 feet deep; bring cold-weather 4-season tent and winter sleeping pads.",
        "summer_profile": "Lush sugar pine and fir forest, half-mile of pristine Lake Tahoe sandy shoreline, pier swimming, tours of historic 1903 Ehrman Mansion, and mountain bike trails connecting to Meeks Bay.",
        "nearby_hikes_attractions": "General Creek Trail, D.L. Bliss / Rubicon Trail connection, Ehrman Mansion, Olympic 1960 Nordic trails, Sugar Pine beach",
        "description": "Lake Tahoe's ultimate year-round destination. In winter, camp directly in deep powdery snow with the luxury of heated restrooms; in summer, enjoy quiet sandy beaches beneath towering 200-foot sugar pines."
    },
    {
        "id": "donner_memorial_sp",
        "name": "Donner Memorial State Park (Donner Lake / Truckee)",
        "region": "Lake Tahoe & Truckee",
        "agency": "California State Parks",
        "lat": 39.3183, "lng": -120.2361,
        "reservation_type": "Paid Reservation",
        "reservation_window": "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "direct_booking_url": "https://www.reservecalifornia.com/Web/#!park/704",
        "overview_url": "https://www.parks.ca.gov/?page_id=503",
        "num_sites": 154,
        "site_types": "Drive-in tent & RV sites, split among 3 wooded loops",
        "nightly_fee": "$35",
        "rating_hiking": 8.5,
        "rating_views": 9.0,
        "rating_comfort": 8.5,
        "rating_competition": 7,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jun – Aug (Summer lake swimming & boating)",
        "light_season": "May & Sep – Oct (Crisp mountain air, fall colors)",
        "winter_profile": "Campground is closed for vehicle camping during heavy winter snows (Nov–Apr), BUT park grounds remain fully open for world-class winter recreation: groomed cross-country ski trails, snowshoe rentals, and the heated Donner Memorial Visitor Center museum. Just 15 minutes from Palisades Tahoe, Alpine Meadows, Sugar Bowl, and Northstar ski resorts.",
        "summer_profile": "Located directly on the east shore of Donner Lake. Sandy swim beach at China Cove, paddleboard/kayak rentals, trout fishing, and shaded picnic areas under lodgepole pine and white fir.",
        "nearby_hikes_attractions": "Donner Summit Canyon Trail, Pacific Crest Trail (Donner Pass), Historic China Wall, Emigrant Trail Museum, Truckee River",
        "description": "Steeped in pioneer history along the shores of Donner Lake in Truckee. Perfect summer alpine basecamp, and a premier winter snowshoeing and Nordic skiing destination."
    },
    {
        "id": "william_kent",
        "name": "William Kent Campground (North Lake Tahoe / Tahoe City)",
        "region": "Lake Tahoe Basin",
        "agency": "US Forest Service (Lake Tahoe Basin MU)",
        "lat": 39.1417, "lng": -120.1583,
        "reservation_type": "Paid Reservation",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232770",
        "overview_url": "https://www.fs.usda.gov/recarea/ltbmu/recarea/?recid=11786",
        "num_sites": 81,
        "site_types": "Drive-in tent, RV sites (some electric hookups), yurt sites",
        "nightly_fee": "$36 - $50",
        "rating_hiking": 8.5,
        "rating_views": 9.0,
        "rating_comfort": 8.0,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (Peak North Lake Tahoe beach season)",
        "light_season": "May – Jun & Sep – Oct",
        "winter_profile": "Closed for vehicle camping in winter. In winter, this location serves as a prime access point: 10 minutes to Palisades Tahoe / Alpine Meadows, 5 minutes to Tahoe City Winter Sports Park (groomed XC skiing, ice skating, snowshoeing).",
        "summer_profile": "Prime North Lake Tahoe location in Sunnyside. Walk across Highway 89 directly onto William Kent Public Beach for swimming and sunset views over the East Shore. Shaded by majestic Jeffrey pines.",
        "nearby_hikes_attractions": "Tahoe Rim Trail (Ward Creek trailhead), Stanford Rock trail, Page Meadows mountain biking, Tahoe City marina",
        "description": "The best-located federal campground on North Lake Tahoe. Minutes from Tahoe City's cafes and lakeside pathways, with beach access across the street."
    },
    {
        "id": "meeks_bay",
        "name": "Meeks Bay Campground & Resort (West Shore Sugar Sand Beach)",
        "region": "Lake Tahoe Basin",
        "agency": "US Forest Service / Washoe Tribe",
        "lat": 39.0347, "lng": -120.1256,
        "reservation_type": "Paid Reservation",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov (extremely coveted)",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232840",
        "overview_url": "https://www.meeksbayresort.com/",
        "num_sites": 40,
        "site_types": "Tent and RV campsites steps from shoreline",
        "nightly_fee": "$38",
        "rating_hiking": 9.0,
        "rating_views": 10.0,
        "rating_comfort": 7.5,
        "rating_competition": 9,
        "competition_badge": "Extreme (9-10/10)",
        "peak_season": "Jun – Sep (Sells out in minutes)",
        "light_season": "Late May & late Sep",
        "winter_profile": "Vehicle campground closed Nov–Apr under feet of snow. Serves as winter backcountry departure point for snowshoers entering the snowbound Meeks Creek valley into Desolation Wilderness.",
        "summer_profile": "Legendary wide, powdery white sugar-sand beach on Lake Tahoe with Caribbean-turquoise shallow water ideal for swimming and stand-up paddleboarding. Marina, boat rentals, and snack shack.",
        "nearby_hikes_attractions": "Meeks Creek Trail (into northern Desolation Wilderness & Rubicon Lake), Rubicon Trail, Sugar Pine Point",
        "description": "Widely acclaimed as the prettiest beach setting on Lake Tahoe. Golden sand, crystal azure water, and direct trailhead into the granite heart of Desolation Wilderness."
    },
    {
        "id": "kaspian_blackwood",
        "name": "Kaspian Campground & Blackwood Canyon Sno-Park (North Shore)",
        "region": "Lake Tahoe Basin",
        "agency": "US Forest Service (Lake Tahoe Basin MU)",
        "lat": 39.1128, "lng": -120.1558,
        "reservation_type": "Paid Reservation (Summer) / Sno-Park Permit (Winter)",
        "reservation_window": "6 months rolling on Recreation.gov (Summer) / CA Sno-Park Permit ($15 day / $40 season) in winter",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232839",
        "overview_url": "https://ohv.parks.ca.gov/?page_id=1233",
        "num_sites": 9,
        "site_types": "Tent-only sites (Summer) + California Sno-Park winter backcountry parking",
        "nightly_fee": "$24 (summer) / $15 Sno-Park permit",
        "rating_hiking": 9.0,
        "rating_views": 9.0,
        "rating_comfort": 6.0,
        "rating_competition": 6,
        "competition_badge": "Moderate (5-6/10)",
        "peak_season": "Jul – Aug (Tent camp) & Dec – Mar (Winter snow sports)",
        "light_season": "Spring & Fall",
        "winter_profile": "HOME OF BLACKWOOD CANYON SNO-PARK: In winter, this is North Lake Tahoe's epicenter for winter backcountry recreation! Plowed staging area for snowmobiling up Blackwood Canyon to Barker Pass (PCT), backcountry ski touring to Ellis Peak (8,740 ft), and snowshoeing along Blackwood Creek. Requires California Sno-Park permit.",
        "summer_profile": "Intimate 9-site tent-only campground directly across from Lake Tahoe. Paved bicycle path connects north to Tahoe City and south to Sugar Pine Point. Picnic tables and beach access.",
        "nearby_hikes_attractions": "Blackwood Canyon, Barker Pass (PCT), Ellis Peak, Eagle Rock volcanic outcrop hike (epic Tahoe vista)",
        "description": "A hidden gem on the North/West Shore. In summer, an uncrowded tent-only sanctuary across from the lake; in winter, the premier Sno-Park gateway for backcountry skiing, snowmobiling, and snowshoeing up Barker Pass."
    },
    {
        "id": "spooner_lake",
        "name": "Lake Tahoe-Nevada State Park (Spooner Lake & Sand Harbor)",
        "region": "Lake Tahoe Basin",
        "agency": "Nevada State Parks",
        "lat": 39.1067, "lng": -119.9042,
        "reservation_type": "Paid Reservation",
        "reservation_window": "11 months rolling on ReserveAmerica / Nevada State Parks",
        "direct_booking_url": "https://www.reserveamerica.com/explore/spooner-lake-and-marlette-flume-state-park/NV/1000000/overview",
        "overview_url": "https://parks.nv.gov/parks/lake-tahoe-nevada-state-park",
        "num_sites": 15,
        "site_types": "Rustic wilderness cabins & walk-in campsites at Spooner Lake",
        "nightly_fee": "$25 ($85 cabins)",
        "rating_hiking": 9.5,
        "rating_views": 10.0,
        "rating_comfort": 7.0,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (Sand Harbor swimming) & Jan – Feb (Winter XC skiing)",
        "light_season": "May – Jun & Sep – Oct (Aspen fall colors at Spooner)",
        "winter_profile": "Spooner Lake transforms into a winter wonderland with over 12 km of groomed and ungroomed cross-country ski and snowshoe trails winding through quiet aspen groves and pine forests. Sledding hills and snowshoe rentals at the visitor center.",
        "summer_profile": "Gateway to the world-famous Marlette Lake Flume Trail (cliffside mountain biking looking 1,500 ft down into Tahoe) and 10 minutes from Sand Harbor's boulder-studded turquoise coves.",
        "nearby_hikes_attractions": "Flume Trail, Marlette Lake, Tahoe Rim Trail, Sand Harbor crystal waters, Shakespeare Festival",
        "description": "On the scenic East/North Shore of Lake Tahoe. Spooner Lake offers tranquil high-elevation forest camping and winter Nordic trails, with quick access to the Caribbean-blue waters of Sand Harbor."
    }
]

# NEW CATEGORY 2: Sierra National Wilderness Areas & Eastern Sierra Attractions
sierra_wilderness_campgrounds = [
    {
        "id": "desolation_wilderness",
        "name": "Desolation Wilderness (Eagle Falls & Bayview / Echo Lakes)",
        "region": "Sierra Wilderness Areas",
        "agency": "US Forest Service (Eldorado NF)",
        "lat": 38.9486, "lng": -120.0883,
        "reservation_type": "Paid Wilderness Permit (Rec.gov) + FCFS Campgrounds",
        "reservation_window": "Wilderness backpacking quota permits open 6 months rolling at 7:00 AM PT on Recreation.gov; Bayview campground is FCFS",
        "direct_booking_url": "https://www.recreation.gov/permits/233261",
        "overview_url": "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78424",
        "num_sites": 12,
        "site_types": "Trailhead FCFS campsites + unlimited backcountry granite wilderness camping across 63,960 acres",
        "nightly_fee": "$10/person/night + permit fee",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 2.0,
        "rating_competition": 9,
        "competition_badge": "Extreme (9-10/10)",
        "peak_season": "Jul – Sep (Alpine lakes thawed and warm)",
        "light_season": "Oct – Nov (Before big snow) & Jun (Early snowmelt)",
        "winter_profile": "EXTREME ALPINE WINTER WILDERNESS: In winter, Desolation is buried under 10–25 feet of snow. World-renowned terrain for experienced mountaineers, splitboarders, and ski tourers tackling Mount Tallac (9,735 ft) and Jake's Peak. Avalanche transceiver, probe, shovel, and AIARE training essential.",
        "summer_profile": "California's most beloved wilderness. Glaciated granite slabs, sapphire alpine tarns (Lake Aloha, Velma Lakes, Susie Lake, Fontanilis Lake), cascading waterfalls, and the Pacific Crest Trail.",
        "nearby_hikes_attractions": "Lake Aloha (granite archipelago), Mount Tallac summit (panoramic view of all of Lake Tahoe), Eagle Falls, Velma Lakes",
        "description": "63,960 acres of pure alpine granite wonder rising directly above southwest Lake Tahoe. A bucket-list backpacking wonderland in summer and serious backcountry mountaineering terrain in winter."
    },
    {
        "id": "mokelumne_wilderness_carson",
        "name": "Mokelumne Wilderness (Woods Lake & Carson Pass)",
        "region": "Sierra Wilderness Areas",
        "agency": "US Forest Service (Eldorado NF)",
        "lat": 38.6942, "lng": -119.9881,
        "reservation_type": "Paid Reservation + FCFS (Woods Lake) / Free Wilderness Permit",
        "reservation_window": "Woods Lake on Recreation.gov (6 months rolling); Wilderness backpacking self-issued at Carson Pass station",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232049",
        "overview_url": "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78426",
        "num_sites": 25,
        "site_types": "Drive-in tent sites at Woods Lake (8,200 ft) + backcountry wilderness",
        "nightly_fee": "$28",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 4.0,
        "rating_competition": 7,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (Legendary wildflower bloom at Winnemucca Lake)",
        "light_season": "Sep – Oct (Golden autumn foliage & brisk hiking)",
        "winter_profile": "HOME OF CARSON PASS SNO-PARK: Carson Pass (8,574 ft) is one of the highest maintained winter passes in California (Hwy 88). Heavy winter snowfall makes it a premier haven for snowshoers and XC skiers trekking to frozen Frog Lake and Winnemucca Lake.",
        "summer_profile": "Renowned for California's most spectacular alpine wildflower displays in July along the trail to Winnemucca Lake and Round Top (10,381 ft). Woods Lake offers tranquil trout fishing and direct trailheads.",
        "nearby_hikes_attractions": "Round Top peak, Winnemucca Lake, Fourth of July Lake, Pacific Crest Trail (Carson Pass), Caples Lake",
        "description": "High-altitude wonderland on Carson Pass. Famous for wildflower superblooms beneath rugged volcanic spires in summer, and deep, quiet snowshoe trails in winter."
    },
    {
        "id": "emigrant_wilderness_kennedy",
        "name": "Emigrant Wilderness (Kennedy Meadows / Sonora Pass)",
        "region": "Sierra Wilderness Areas",
        "agency": "US Forest Service (Stanislaus NF)",
        "lat": 38.3006, "lng": -119.7428,
        "reservation_type": "First-Come, First-Served / Free Wilderness Permit",
        "reservation_window": "Campground is 100% FCFS ($20); Wilderness backpacking permits are FREE and self-issued at Summit Ranger Station on Hwy 108",
        "direct_booking_url": "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981",
        "overview_url": "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981",
        "num_sites": 45,
        "site_types": "Drive-in riverside campsites + 113,000 acres of uncrowded wilderness backpacking",
        "nightly_fee": "$20 (trailhead) / $0 (wilderness)",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 4.0,
        "rating_competition": 5,
        "competition_badge": "Moderate (5-6/10)",
        "peak_season": "Jul – Sep (High mountain passes snow-free)",
        "light_season": "Jun & Oct",
        "winter_profile": "Sonora Pass (Hwy 108) closes completely with the first major winter storm (typically November to May). Kennedy Meadows is inaccessible by car in deep winter.",
        "summer_profile": "The uncrowded sister to Yosemite. Smooth glaciated granite bowls, clear trout-filled streams (Middle Fork Stanislaus River), pack horses, and sprawling alpine trail networks leading to Relief Reservoir and High Emigrant Basin.",
        "nearby_hikes_attractions": "Relief Reservoir, Kennedy Lake, Sonora Pass (9,624 ft) PCT crossing, Leavitt Falls, Columns of the Giants basalt formations",
        "description": "Bordering Yosemite National Park to the north, Emigrant Wilderness delivers raw High Sierra granite, cascading rivers, and backcountry isolation without Yosemite's crowds or lottery restrictions."
    },
    {
        "id": "june_lake_loop",
        "name": "June Lake Loop (Oh! Ridge Campground / Ansel Adams Gateway)",
        "region": "Eastern Sierra & Mono County",
        "agency": "US Forest Service (Inyo NF)",
        "lat": 37.7858, "lng": -119.0683,
        "reservation_type": "Paid Reservation + FCFS",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232014",
        "overview_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20562",
        "num_sites": 144,
        "site_types": "Drive-in tent and RV sites perched above sandy lake beach",
        "nightly_fee": "$34",
        "rating_hiking": 9.5,
        "rating_views": 10.0,
        "rating_comfort": 7.5,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (Summer lake fun) & late Sep – Oct (World-class golden fall foliage)",
        "light_season": "May & Nov",
        "winter_profile": "Campground closes mid-October due to freezing temperatures. However, June Lake transforms into a cozy winter haven: June Mountain ski resort (renowned as 'The Family Mountain' with steep backcountry bowls and uncrowded powder) opens Dec–April.",
        "summer_profile": "Perched on a sandy bluff above June Lake with swimming beach, trout fishing, kayak rentals, and jaw-dropping views of Carson Peak (10,909 ft) rising sheer from the water. Autumn brings unmatched golden aspen leaf-peeping.",
        "nearby_hikes_attractions": "Parker Lake trail, Fern Lake, Rush Creek Trail into Ansel Adams Wilderness & Thousand Island Lake, Gull Lake, Silver Lake",
        "description": "Known as the 'Switzerland of California.' Located along the horseshoe scenic June Lake Loop in the Eastern Sierra, boasting dramatic glacial peaks, sandy swimming beaches, and autumn aspen superblooms."
    },
    {
        "id": "mammoth_lakes_coldwater",
        "name": "Mammoth Lakes Basin (Coldwater & Lake Mary / Devils Postpile)",
        "region": "Eastern Sierra & Mono County",
        "agency": "US Forest Service (Inyo NF)",
        "lat": 37.5956, "lng": -118.9958,
        "reservation_type": "Paid Reservation",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232009",
        "overview_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20572",
        "num_sites": 74,
        "site_types": "Drive-in tent and RV sites at 9,000 ft elevation",
        "nightly_fee": "$32",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 7.0,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Aug (High alpine summer) & Nov – Apr (Mammoth Mountain ski season)",
        "light_season": "Jun & Sep – Oct",
        "winter_profile": "WORLD-CLASS WINTER SPORTS CAPITAL: The campground is buried under heavy snow (closes Oct–May), but Mammoth Lakes is California's premier ski & snowboard destination. Mammoth Mountain (11,053 ft) offers 3,500 acres of terrain and often stays open into July. Winter snowshoeing, snowmobiling, and cross-country skiing at Tamarack Lodge.",
        "summer_profile": "Located in the high alpine Mammoth Lakes Basin at 9,000 feet. Direct trailhead access to Duck Pass, Emerald Lake, and Barney Lake. Minutes from Devils Postpile National Monument and Rainbow Falls.",
        "nearby_hikes_attractions": "Duck Pass Trail, Devils Postpile geometric basalt columns, Rainbow Falls (101-ft cascade), Crystal Lake, Mammoth Crest",
        "description": "High-elevation alpine wonderland at 9,000 feet in the Eastern Sierra. Steps from sparkling glacier lakes, surreal volcanic geology at Devils Postpile, and epic John Muir Wilderness trailheads."
    },
    {
        "id": "convict_lake",
        "name": "Convict Lake Campground (Eastern Sierra Dramatic Basin)",
        "region": "Eastern Sierra & Mono County",
        "agency": "US Forest Service (Inyo NF)",
        "lat": 37.5978, "lng": -118.8522,
        "reservation_type": "Paid Reservation + FCFS",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232013",
        "overview_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20560",
        "num_sites": 85,
        "site_types": "Tent and RV sites along Convict Creek beneath towering cliffs",
        "nightly_fee": "$34",
        "rating_hiking": 9.0,
        "rating_views": 10.0,
        "rating_comfort": 7.5,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jun – Aug (Summer fishing) & Oct (Fall foliage reflection)",
        "light_season": "May & Sep",
        "winter_profile": "Campground closes for winter in late October. However, the lake road is plowed year-round, allowing breathtaking winter day visits to photograph Mount Morrison's sheer snow-dusted rock face reflecting on ice-free blue waters.",
        "summer_profile": "One of the most photogenic alpine lakes in the world. Mount Morrison rises 4,000 vertical feet directly from the shoreline. Easy 3-mile loop trail hugs the shoreline through aspens and over boardwalks.",
        "nearby_hikes_attractions": "Convict Lake Loop Trail, Convict Creek Canyon Trail to Lake Genevieve (John Muir Wilderness), Hot Creek Geologic Site, Whitmore Hot Springs",
        "description": "Framed by dramatic, steep metamorphic rock walls and cobalt-blue water. Home to trophy rainbow trout, fall foliage, and quick access to natural Eastern Sierra hot springs."
    },
    {
        "id": "big_pine_creek",
        "name": "Big Pine Creek Campground (Palisade Glacier & Turquoise Lakes)",
        "region": "Eastern Sierra & Inyo County",
        "agency": "US Forest Service (Inyo NF)",
        "lat": 37.1264, "lng": -118.4383,
        "reservation_type": "Paid Reservation + FCFS",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232016",
        "overview_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20268",
        "num_sites": 30,
        "site_types": "Drive-in tent and RV sites along roaring glacier-fed Big Pine Creek (7,700 ft)",
        "nightly_fee": "$28",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 5.0,
        "rating_competition": 8,
        "competition_badge": "High (7-8/10)",
        "peak_season": "Jul – Sep (Glacial lakes thawed into vibrant turquoise)",
        "light_season": "Jun & Oct",
        "winter_profile": "Campground closed in winter (Nov–Apr); road closed at lower glacier gate due to snow. Extreme mountaineers use it for winter ascents of the Palisade Glacier.",
        "summer_profile": "Trailhead for the famed North Fork Big Pine Creek trail to Seven Lakes—fed by Palisade Glacier (the southernmost glacier in North America). The glacial flour gives these alpine tarns an otherworldly turquoise-milky glow beneath the colossal granite fortress of Temple Crag (12,999 ft).",
        "nearby_hikes_attractions": "Temple Crag, Big Pine Lakes 1-7, Palisade Glacier, South Fork Big Pine Creek to Brainerd Lake, Ancient Bristlecone Pine Forest (White Mountains nearby)",
        "description": "The gateway to California's most breathtaking turquoise alpine lakes. Camp along rushing creek waters at 7,700 feet, then hike up into the shadow of 14,000-foot peaks."
    },
    {
        "id": "whitney_portal",
        "name": "Whitney Portal Campground (Mount Whitney Summit Basecamp)",
        "region": "Eastern Sierra & Inyo County",
        "agency": "US Forest Service (Inyo NF)",
        "lat": 36.5869, "lng": -118.2397,
        "reservation_type": "Paid Reservation + FCFS",
        "reservation_window": "6 months rolling at 7:00 AM PT on Recreation.gov (Very competitive; summit permits via annual lottery in February)",
        "direct_booking_url": "https://www.recreation.gov/camping/campgrounds/232017",
        "overview_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20696",
        "num_sites": 43,
        "site_types": "Drive-in tent sites nestled in thick pine forest at 8,360 ft",
        "nightly_fee": "$30",
        "rating_hiking": 10.0,
        "rating_views": 10.0,
        "rating_comfort": 6.0,
        "rating_competition": 9,
        "competition_badge": "Extreme (9-10/10)",
        "peak_season": "Jul – Sep (Mount Whitney summit snow-free window)",
        "light_season": "May – Jun & Oct",
        "winter_profile": "Whitney Portal Road closes in winter near the base (at road gate). Heavy snow blankets the canyon; only accessible on foot/skis by experienced technical mountaineers tackling the Mountaineer's Route in winter conditions.",
        "summer_profile": "The official starting point for hiking Mount Whitney (14,505 ft, highest peak in the contiguous US). Shaded by giant ponderosa and Jeffrey pines alongside roaring waterfalls and the historic Whitney Portal Store (famed giant pancakes).",
        "nearby_hikes_attractions": "Mount Whitney Trail (22 miles round trip, 6,100 ft elevation gain), Lone Pine Lake (no permit required day-hike), Meysan Lake, Alabama Hills",
        "description": "Perched at 8,360 feet in a sheer granite amphitheater at the base of Mount Whitney. The ultimate acclimatization basecamp for tackling the highest peak in the Lower 48."
    },
    {
        "id": "alabama_hills",
        "name": "Alabama Hills National Scenic Area (Dispersed BLM / Lone Pine)",
        "region": "Eastern Sierra & Inyo County",
        "agency": "Bureau of Land Management (BLM)",
        "lat": 36.6083, "lng": -118.1153,
        "reservation_type": "Dispersed / Designated Semi-Primitive (Free / No Permit)",
        "reservation_window": "No reservations - Designated dispersed sites (Free $0). Follow BLM designated camping posts to protect fragile desert ecology.",
        "direct_booking_url": "https://www.blm.gov/programs/national-conservation-lands/california/alabama-hills-national-scenic-area",
        "overview_url": "https://www.blm.gov/programs/national-conservation-lands/california/alabama-hills-national-scenic-area",
        "num_sites": 50,
        "site_types": "Primitive vehicle dispersed campsites nestled in golden granite boulder mazes",
        "nightly_fee": "Free ($0)",
        "rating_hiking": 8.5,
        "rating_views": 10.0,
        "rating_comfort": 1.5,
        "rating_competition": 5,
        "competition_badge": "Moderate (5-6/10)",
        "peak_season": "Oct – Apr (Pleasant winter/spring desert temperatures)",
        "light_season": "Jun – Aug (Blistering 105°F desert heat)",
        "winter_profile": "PRIME WINTER CAMPING DESTINATION! While the high Sierra peaks above are frozen under 15 feet of snow, the Alabama Hills (elevation 4,500 ft) enjoy crisp, sunny winter days (55–65°F) and cool nights. Unmatched winter photography with rounded warm rocks framing snow-capped Mount Whitney.",
        "summer_profile": "Extremely hot in mid-summer (frequently exceeds 100°F). Sunrise and sunset are magical; explore natural rock arches (Mobius Arch) and historic movie locations where hundreds of Hollywood westerns and Iron Man were filmed.",
        "nearby_hikes_attractions": "Mobius Arch Loop Trail, Movie Road, Shark's Tooth, Mount Whitney Fish Hatchery, Museum of Western Film History in Lone Pine",
        "description": "World-famous golden granite rock arches and rounded labyrinth boulders sitting directly beneath the towering 14,000-foot snow-capped eastern face of the Sierra Nevada. Phenomenal winter dispersed camping and astrophotography."
    },
    {
        "id": "mono_lake_travertine",
        "name": "Mono Lake Tufa Reserve & Travertine Hot Springs (Bridgeport / Lee Vining)",
        "region": "Eastern Sierra & Mono County",
        "agency": "California State Parks / BLM",
        "lat": 38.0019, "lng": -119.1417,
        "reservation_type": "Dispersed BLM / First-Come First-Served",
        "reservation_window": "Free BLM dispersed camping nearby (Travertine Hot Springs / Bridgeport) & USFS campgrounds at Tioga Pass / Lee Vining Canyon",
        "direct_booking_url": "https://www.monolake.org/",
        "overview_url": "https://www.parks.ca.gov/?page_id=514",
        "num_sites": 40,
        "site_types": "BLM dispersed sites and USFS creek-side campgrounds (Lundy Canyon / Moraine)",
        "nightly_fee": "$0 - $22",
        "rating_hiking": 8.5,
        "rating_views": 10.0,
        "rating_comfort": 4.0,
        "rating_competition": 4,
        "competition_badge": "Accessible (2-4/10)",
        "peak_season": "May – Oct",
        "light_season": "Nov – Apr",
        "winter_profile": "Travertine Hot Springs remains accessible in winter (unless heavy unplowed snow on final dirt road section). Soaking in natural 103°F mineral pools while surrounded by winter snowdrifts overlooking the Sawtooth Ridge is an iconic Eastern Sierra winter ritual.",
        "summer_profile": "Explore the eerie, ancient limestone tufa towers rising from 1-million-year-old saline Mono Lake. Gateway to Bodie Ghost Town and Tioga Pass (Highway 120 entrance into Tuolumne Meadows).",
        "nearby_hikes_attractions": "South Tufa Reserve boardwalk, Travertine Hot Springs, Buckeye Hot Springs, Bodie State Historic Park (abandoned gold mining ghost town), Lundy Canyon waterfalls",
        "description": "Surreal desert-meets-mountain crossroads. Natural hot mineral springs with mountain vistas, eerie tufa towers at Mono Lake, and the remarkably preserved historic ghost town of Bodie."
    }
]

# Calculate distances and metrics for new campgrounds
all_new = tahoe_campgrounds + sierra_wilderness_campgrounds
for c in all_new:
    dist_straight, dist_road, drive_time = calc_dist(c["lat"], c["lng"])
    c["distance_straight_miles"] = dist_straight
    c["distance_road_miles"] = dist_road
    c["drive_time_from_home"] = drive_time
    c["composite_score_out_of_10"] = round((c["rating_hiking"] * 0.35) + (c["rating_views"] * 0.35) + (c["rating_comfort"] * 0.30), 1)

# Combine all: existing 53 + new 16 = 69 campgrounds!
combined_cgs = list(cgs_dict.values()) + all_new

# Sort strictly by driving distance from Home
combined_cgs.sort(key=lambda x: x["distance_road_miles"])

data_payload = {
    "home_point": HOME,
    "total_campgrounds": len(combined_cgs),
    "campgrounds": combined_cgs
}

with open("campgrounds_data.json", "w") as f:
    json.dump(data_payload, f, indent=2)

print(f"Successfully generated expanded campgrounds_data.json with {len(combined_cgs)} campgrounds!")
