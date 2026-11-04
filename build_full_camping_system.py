# build_full_camping_system.py
import json
from data_builder import make_cg, HOME

all_cgs = [
    # -------------------------------------------------------------
    # 1. SAN FRANCISCO & IMMEDIATE MARIN HEADLANDS
    # -------------------------------------------------------------
    make_cg(
        "rob_hill", "Rob Hill Campground", "Presidio of San Francisco", "San Francisco", "Presidio Trust / NPS",
        37.7963, -122.4746, "Paid Reservation", "Opens in February for entire season (Apr-Oct) at 9:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/10058778", "https://www.presidio.gov/places/rob-hill-campground",
        4, "Group / Tent camping (up to 30 people per site)", "$135 - $175 / group site",
        6.5, 8.5, 8.0, 8, "May – Sep", "Closed Nov – Mar",
        "Closed for winter (open Apr–Oct only). Wet cypress coastal fog, crisp ocean breeze.",
        "The only public campground in San Francisco! Perched in a cypress grove overlooking Baker Beach and the Pacific Ocean.",
        "Presidio Promenade, Battery Godfrey, Immigrant Point, Coastal Trail to Baker Beach"
    ),
    make_cg(
        "kirby_cove", "Kirby Cove Campground", "Marin Headlands (GGNRA)", "Marin / SF Bay", "National Park Service (GGNRA)",
        37.8286, -122.4939, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov (extremely competitive)",
        "https://www.recreation.gov/camping/campgrounds/232490", "https://www.nps.gov/goga/planyourvisit/kirby.htm",
        5, "Walk-in tent sites (1 day-use group site)", "$40",
        8.5, 10.0, 5.0, 10, "May – Oct", "Nov – Mar (Crisp & foggy)",
        "Open year-round; chilly coastal winds, heavy fog, but stunning crisp winter sunsets framing Golden Gate Bridge.",
        "Unrivaled view directly facing the Golden Gate Bridge and SF skyline from a sheltered beach cove. Sells out within milliseconds of release.",
        "Golden Gate Bridge bluff views, Hawk Hill, Coastal Trail, Black Sands Beach"
    ),
    make_cg(
        "bicentennial", "Bicentennial Campground", "Marin Headlands (GGNRA)", "Marin / SF Bay", "National Park Service (GGNRA)",
        37.8291, -122.5292, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/273836", "https://www.nps.gov/goga/planyourvisit/camp-bicentennial.htm",
        3, "Walk-in tent sites (100-200m from car)", "$35",
        8.0, 8.5, 4.0, 7, "Apr – Oct", "Nov – Mar",
        "Open year-round; cold ocean winds, vault toilets only, pack all water in.",
        "Marin Headlands ocean vistas, easiest walk-in camp in the Headlands near historic batteries and Rodeo Beach.",
        "Rodeo Lagoon, Point Bonita Lighthouse, Battery Mendell, Coastal Trail"
    ),
    make_cg(
        "haypress", "Haypress Campground", "Marin Headlands (GGNRA)", "Marin / SF Bay", "National Park Service (GGNRA)",
        37.8542, -122.5361, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/273835", "https://www.nps.gov/goga/planyourvisit/camp-haypress.htm",
        5, "Hike-in backcountry tent sites (0.75 mi hike from Tennessee Valley parking)", "$30",
        9.0, 8.5, 3.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; pack in all water; muddy trails after winter rains. Very peaceful valley setting.",
        "Tucked into the lush floor of Tennessee Valley. An easy 0.75-mile hike from the trailhead makes it ideal for beginner backpackers.",
        "Tennessee Valley Trail, Tennessee Beach, Coastal Trail, Rhubarb Trail"
    ),
    make_cg(
        "hawkcamp", "Hawkcamp Campground", "Marin Headlands (GGNRA)", "Marin / SF Bay", "National Park Service (GGNRA)",
        37.8465, -122.5342, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/273835", "https://www.nps.gov/goga/planyourvisit/camp-haypress.htm",
        3, "Backcountry hike-in tent sites (3 mi uphill hike via Bobcat or Miwok trail)", "$30",
        9.5, 9.5, 2.5, 8, "May – Oct", "Nov – Mar",
        "Open year-round; exposed high-ridge backcountry site with strong marine winds; bring all water and wind-rated tent.",
        "Perched high on a ridge at 1,000 ft elevation with panoramic views of the Marin Headlands, SF Bay, and the Pacific.",
        "Bobcat Trail, Miwok Trail, Coastal Trail, Hawk Hill raptor migration"
    ),

    # -------------------------------------------------------------
    # 2. MOUNT TAMALPAIS STATE PARK
    # -------------------------------------------------------------
    make_cg(
        "pantoll", "Pantoll Campground", "Mount Tamalpais State Park", "Marin / SF Bay", "California State Parks",
        37.9048, -122.6041, "First-Come, First-Served", "100% First-Come, First-Served year-round (open 365 days). For weekend stays arrive by Friday 8:00 AM.",
        "https://www.parks.ca.gov/?page_id=471", "https://www.parks.ca.gov/?page_id=471",
        16, "Walk-in tent sites under towering Douglas firs and coastal oaks", "$25",
        10.0, 8.5, 6.0, 8, "May – Oct (Fills by Friday 10 AM)", "Nov – Mar (Walk-in availability)",
        "Open 365 days a year! Winter brings rushing waterfalls on Steep Ravine and Cataract trails, lush green moss, and fewer crowds.",
        "The premier trail hub of Mt. Tamalpais. Direct trailhead access to the famed Dipsea Trail, Steep Ravine Trail, and Matt Davis Trail.",
        "Dipsea Trail, Steep Ravine Trail, Matt Davis Trail, Stinson Beach, Cataract Falls"
    ),
    make_cg(
        "bootjack", "Bootjack Campground", "Mount Tamalpais State Park", "Marin / SF Bay", "California State Parks",
        37.9083, -122.5972, "First-Come, First-Served", "100% First-Come, First-Served year-round. Arrive early Friday morning for weekend stays.",
        "https://www.parks.ca.gov/?page_id=471", "https://www.parks.ca.gov/?page_id=471",
        15, "Walk-in tent sites in sheltered redwood and bay laurel canyon", "$25",
        9.5, 8.0, 6.0, 7, "May – Oct", "Nov – Mar",
        "Open 365 days a year; quiet, secluded redwood canyon with flowing creek in winter and spring.",
        "Located 0.7 miles east of Pantoll along Panoramic Highway. Quieter and more sheltered than Pantoll, with direct access to Bootjack Trail.",
        "Bootjack Trail, Mountain Theater, Old Mine Trail, Dipsea Trail connection"
    ),
    make_cg(
        "steep_ravine_cabins", "Steep Ravine Cabins", "Mount Tamalpais State Park", "Marin / SF Bay", "California State Parks",
        37.8988, -122.6394, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia (sells out in under 2 seconds)",
        "https://www.reservecalifornia.com/Web/#!park/705", "https://www.parks.ca.gov/?page_id=471",
        10, "Historic rustic wood oceanfront cabins with wood-burning stoves", "$100",
        10.0, 10.0, 7.5, 10, "Year-Round (Extremely coveted)", "Winter storm watching (Coveted)",
        "Open year-round; wood-burning cast-iron stoves keep historic rustic cabins cozy during dramatic Pacific winter rainstorms.",
        "Perched directly on rugged Pacific cliffs on Rocky Point. No electricity; kerosene or wood stove heating. California's most coveted stay.",
        "Rocky Point tidepools, Dipsea Trail, Stinson Beach, Steep Ravine redwoods"
    ),
    make_cg(
        "steep_ravine_camps", "Steep Ravine Environmental Campsites", "Mount Tamalpais State Park", "Marin / SF Bay", "California State Parks",
        37.8992, -122.6385, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/705", "https://www.parks.ca.gov/?page_id=471",
        7, "Primitive walk-in bluff tent sites (100-300 yards from parking)", "$25",
        10.0, 10.0, 4.5, 10, "Year-Round", "Winter (Brisk ocean winds)",
        "Open year-round; dramatic winter surf, open marine exposure. Bring heavy-duty tent stakes.",
        "Camp on the coastal terrace bluffs overlooking crashing Pacific breakers and rocky tidepools.",
        "Rocky Point, Dipsea Trail, Stinson Beach, Steep Ravine Trail"
    ),

    # -------------------------------------------------------------
    # 3. ANGEL ISLAND STATE PARK
    # -------------------------------------------------------------
    make_cg(
        "angel_island_ridge", "Angel Island Ridge Campsites", "Angel Island State Park", "Marin / SF Bay", "California State Parks",
        37.8609, -122.4326, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/670", "https://www.parks.ca.gov/?page_id=468",
        3, "Walk-in ridge primitive sites (Sites 1, 2, 3)", "$30",
        8.5, 10.0, 4.0, 9, "May – Oct", "Nov – Mar",
        "Open year-round; brisk bay winds, jaw-dropping panoramic views of the Golden Gate Bridge and SF nighttime skyline.",
        "Unbeatable nighttime panorama of San Francisco skyscrapers lit up across the water.",
        "Mt. Caroline Livermore peak, Perimeter Trail, Immigration Station"
    ),
    make_cg(
        "angel_island_sunrise", "Angel Island Sunrise Campsites", "Angel Island State Park", "Marin / SF Bay", "California State Parks",
        37.8645, -122.4281, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/670", "https://www.parks.ca.gov/?page_id=468",
        3, "Walk-in east-facing primitive sites (Sites 4, 5, 6)", "$30",
        8.5, 9.5, 4.0, 8, "May – Oct", "Nov – Mar",
        "Open year-round; sheltered from western winds; spectacular morning sunrise over the East Bay hills.",
        "East-facing campsites looking across the bay toward Berkeley, Oakland, and Mount Diablo.",
        "Perimeter Trail, East Garrison historic military barracks, Fort McDowell"
    ),
    make_cg(
        "angel_island_east_bay", "Angel Island East Bay & Kayak Camps", "Angel Island State Park", "Marin / SF Bay", "California State Parks",
        37.8582, -122.4255, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/670", "https://www.parks.ca.gov/?page_id=468",
        5, "Walk-in & Kayak landing campsites (Sites 7-9 & Kayak Group Site)", "$30 - $40",
        8.0, 9.0, 4.0, 8, "May – Oct", "Nov – Mar",
        "Open year-round; direct paddle craft landing access at Kayak Camp for self-contained sea kayakers.",
        "Sheltered bayside camping with boat/kayak landing beach and views of the East Bay.",
        "Perimeter Trail, Quarry Beach, Angel Island Ferry dock at Ayala Cove"
    ),

    # -------------------------------------------------------------
    # 4. MARIN & POINT REYES NATIONAL SEASHORE
    # -------------------------------------------------------------
    make_cg(
        "china_camp", "China Camp State Park (Back Ranch Meadows)", "China Camp State Park", "Marin / SF Bay", "California State Parks",
        38.0003, -122.4947, "Paid Reservation", "6 months rolling on ReserveCalifornia / Friends of China Camp",
        "https://www.reservecalifornia.com/Web/#!park/716", "https://www.parks.ca.gov/?page_id=466",
        30, "Walk-in tent sites (100-300 yards from parking in oak meadow)", "$35",
        7.5, 7.5, 7.0, 6, "May – Oct", "Nov – Mar",
        "Open year-round; sheltered from coastal fog, mild winter temperatures along San Pablo Bay.",
        "Tucked into warm, sun-drenched oak and bay laurel woodlands along San Pablo Bay. 15 miles of mountain bike singletrack.",
        "Shoreline Trail, historic 1880s Chinese shrimp fishing village, San Pablo Bay kayak launch"
    ),
    make_cg(
        "samuel_p_taylor", "Samuel P. Taylor State Park (Creekside & Madrone)", "Samuel P. Taylor State Park", "Marin / SF Bay", "California State Parks",
        38.0163, -122.7291, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/719", "https://www.parks.ca.gov/?page_id=469",
        60, "Standard drive-in tent, RV (no hookups), plus Madrone rustic cabins", "$35 ($100 cabins)",
        8.5, 8.5, 8.0, 8, "May – Sep", "Nov – Mar (Chilly in redwood canyon)",
        "Open year-round; winter coho salmon spawning runs in Lagunitas Creek, roaring creek, cool redwood canyon floor.",
        "Lush old-growth redwood grove along Lagunitas Creek. Paved car-free path connects directly to West Marin.",
        "Cross Marin Bike Trail, Barnabe Mountain, Pioneer Redwood Tree Trail, Lagunitas Creek salmon run"
    ),
    make_cg(
        "pt_reyes_wildcat", "Point Reyes: Wildcat Camp", "Point Reyes National Seashore", "Marin / SF Bay", "National Park Service",
        37.9712, -122.7885, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233359", "https://www.nps.gov/pore/planyourvisit/campgrounds.htm",
        11, "Hike-in backcountry campsites (5.5 - 6.3 mi hike from Palomarin or Bear Valley)", "$30",
        10.0, 10.0, 4.0, 10, "May – Oct", "Nov – Mar (Gray whale migration)",
        "Open year-round; winter brings thundering surf, whale migration watching, and lush green coastal bluffs.",
        "Located in an open meadow plateau steps from the beach and only 1 mile south of tidefall waterfall Alamere Falls.",
        "Alamere Falls, Wildcat Beach, Ocean Lake Loop, Bass Lake swimming hole"
    ),
    make_cg(
        "pt_reyes_coast", "Point Reyes: Coast Camp", "Point Reyes National Seashore", "Marin / SF Bay", "National Park Service",
        38.0289, -122.8553, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233359", "https://www.nps.gov/pore/planyourvisit/campgrounds.htm",
        14, "Hike-in & Bike-in backcountry campsites (1.8 mi easy walk/bike from Laguna)", "$30",
        9.5, 9.5, 4.5, 9, "May – Oct", "Nov – Mar",
        "Open year-round; broad sandy beach, coastal tidepools, easy bike-in camping option.",
        "Nestled in a grassy coastal hollow 200 meters from Santa Maria Beach. The easiest backcountry camp to reach in Point Reyes.",
        "Santa Maria Beach, Coast Trail to Sculptured Beach, Laguna Trail, Fire Lane Trail"
    ),
    make_cg(
        "pt_reyes_glen", "Point Reyes: Glen Camp", "Point Reyes National Seashore", "Marin / SF Bay", "National Park Service",
        37.9942, -122.7917, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233359", "https://www.nps.gov/pore/planyourvisit/campgrounds.htm",
        12, "Hike-in backcountry campsites (4.6 mi hike from Bear Valley Visitor Center)", "$30",
        9.0, 8.5, 4.0, 8, "May – Oct", "Nov – Mar",
        "Open year-round; deep quiet forest sheltered from coastal ocean fog and high winds.",
        "Tucked into a quiet valley among towering Douglas firs and bishop pines. No ocean view, but maximum wind protection and solitude.",
        "Glen Trail, Stewart Trail, Bear Valley Trail, Mt. Wittenberg summit"
    ),
    make_cg(
        "pt_reyes_sky", "Point Reyes: Sky Camp", "Point Reyes National Seashore", "Marin / SF Bay", "National Park Service",
        38.0378, -122.8256, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233359", "https://www.nps.gov/pore/planyourvisit/campgrounds.htm",
        12, "Hike-in backcountry campsites (1.4 mi uphill hike from Sky Trailhead)", "$30",
        9.5, 9.5, 4.0, 9, "May – Oct", "Nov – Mar",
        "Open year-round; sweeping ocean sunsets overlooking Drakes Bay and Point Reyes headlands.",
        "Perched on the western slope of Mount Wittenberg at 1,025 ft. Spectacular views of Drakes Bay, the Pacific, and coastal fog layers.",
        "Mount Wittenberg Trail, Sky Trail, Meadow Trail, Woodward Valley Trail"
    ),
    make_cg(
        "pt_reyes_tomales_boat", "Point Reyes: Tomales Bay Boat-In Camps", "Point Reyes National Seashore", "Marin / SF Bay", "National Park Service",
        38.1256, -122.9242, "Paid Reservation", "3 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233359", "https://www.nps.gov/pore/planyourvisit/campgrounds.htm",
        20, "Boat-in only wilderness beach campsites along west shore of Tomales Bay", "$30",
        8.5, 9.5, 3.0, 8, "May – Oct", "Nov – Mar (Winter bioluminescence)",
        "Open year-round; kayak-in only; must carry all fresh water and pack out all human waste (portable toilet required).",
        "Wilderness beach camping accessible only by kayak, canoe, or boat. Camp on pristine sandy beaches like Marshall Beach and Tomales Beach.",
        "Tomales Bay paddling, bioluminescent night kayaking, tule elk viewing on Tomales Point"
    ),

    # -------------------------------------------------------------
    # 5. EAST BAY HILLS & DIABLO RANGE
    # -------------------------------------------------------------
    make_cg(
        "anthony_chabot", "Anthony Chabot Regional Park", "Anthony Chabot Regional Park", "East Bay", "East Bay Regional Park District (EBRPD)",
        37.7471, -122.1082, "Paid Reservation", "12 weeks (84 days) rolling in advance on EBRPD portal",
        "https://www.ebparks.org/recreation/camping/anthony-chabot", "https://www.ebparks.org/parks/anthony-chabot",
        75, "Drive-in tent, RV hookup sites, hike-in backpack sites", "$25 - $45",
        7.5, 7.5, 8.0, 6, "May – Oct", "Nov – Mar",
        "Open year-round; eucalyptus and pine forest above Lake Chabot; easy quick getaway.",
        "Forested ridges above Lake Chabot with miles of hiking, mountain biking, and dog-friendly trails.",
        "Lake Chabot loop trail, Honker Bay, Skyline National Recreation Trail, Redwood Regional Park"
    ),
    make_cg(
        "del_valle", "Del Valle Regional Park", "Del Valle Regional Park", "East Bay", "East Bay Regional Park District (EBRPD)",
        37.6163, -121.6974, "Paid Reservation", "12 weeks (84 days) rolling on EBRPD portal",
        "https://www.ebparks.org/recreation/camping/del-valle", "https://www.ebparks.org/parks/del-valle",
        150, "Tent, RV with water/sewer/electric, group sites", "$25 - $45",
        8.0, 8.0, 8.0, 6, "May – Oct", "Nov – Mar",
        "Open year-round; pleasant sunny winter/spring camping; warm swimming in summer.",
        "Surrounded by oak-covered hills with a 5-mile long reservoir for swimming, boating, and deep wilderness backpacking.",
        "5-mile reservoir kayak/paddle, Ohlone Wilderness Trail trailhead, Rose Peak (3,817 ft)"
    ),
    make_cg(
        "mount_diablo_juniper", "Mount Diablo: Juniper Campground", "Mount Diablo State Park", "East Bay", "California State Parks",
        37.8767, -121.9312, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/692", "https://www.parks.ca.gov/?page_id=517",
        36, "Drive-in tent & small RV sites at 3,000 ft elevation", "$30",
        8.5, 9.5, 6.5, 7, "Apr – Oct", "Nov – Feb (Crisp winter clarity)",
        "Open year-round; high elevation brings crisp winter sunsets over SF Bay and sunrise over the Sierra crest.",
        "Perched at 3,000 feet on the shoulder of Mount Diablo. Breathtaking sunset views across the entire San Francisco Bay Area.",
        "Mount Diablo Summit (3,849 ft, 40-county view), Summit Trail, Grand Loop Trail"
    ),
    make_cg(
        "mount_diablo_live_oak", "Mount Diablo: Live Oak Campground", "Mount Diablo State Park", "East Bay", "California State Parks",
        37.8542, -121.9367, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/692", "https://www.parks.ca.gov/?page_id=517",
        14, "Drive-in tent sites nestled in oaks near sandstone outcrops", "$30",
        8.0, 8.5, 6.0, 6, "Apr – Oct", "Nov – Mar",
        "Open year-round; sheltered from high summit winds, pleasant spring oak canopy.",
        "Nestled below Rock City among mossy sandstone boulders and ancient valley oaks. Great for scrambling and exploring caves.",
        "Rock City sandstone mazes, Sentinel Rock, Trail Through Time"
    ),
    make_cg(
        "henry_coe_ranch", "Henry W. Coe: Coe Ranch Campground", "Henry W. Coe State Park", "South Bay / Diablo Range", "California State Parks",
        37.1867, -121.5472, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/715", "https://www.parks.ca.gov/?page_id=561",
        20, "Drive-in sites at 2,600 ft ridge near headquarters", "$20",
        9.0, 8.5, 6.0, 4, "Mar – May (Wildflower superbloom)", "Jun – Aug (Summer heat)",
        "Open year-round; crisp winter camping with emerald green hills and starry night skies.",
        "Perched at 2,600 feet at the park headquarters entrance of Northern California's largest state park (87,000 acres).",
        "Pine Ridge Trail, Middle Ridge, Monument Peak, Hunting Hollow"
    ),
    make_cg(
        "henry_coe_backcountry", "Henry W. Coe: Wilderness Backpacking", "Henry W. Coe State Park", "South Bay / Diablo Range", "California State Parks",
        37.2142, -121.4925, "First-Come, First-Served / Self-Issued", "Self-issued backpacking registration at park headquarters kiosk upon arrival",
        "https://www.parks.ca.gov/?page_id=561", "https://www.parks.ca.gov/?page_id=561",
        50, "Dispersed and designated wilderness trail camps (Mississippi Lake, Poverty Flat)", "$5 / person / night",
        10.0, 9.0, 2.5, 3, "Mar – May (Peak wildflowers)", "Jun – Aug (Very hot)",
        "Open year-round; winter and spring are prime backpacking seasons when seasonal streams and lakes are full.",
        "Over 87,000 acres of open Diablo Range wilderness backpacking solitude with remote fishing lakes and wildflower ridges.",
        "Mississippi Lake, Poverty Flat, Orestimba Wilderness, Mount Sizer (The Shortcut)"
    ),

    # -------------------------------------------------------------
    # 6. PENINSULA, HALF MOON BAY & SANTA CRUZ MOUNTAINS
    # -------------------------------------------------------------
    make_cg(
        "half_moon_bay", "Half Moon Bay State Beach (Francis Beach)", "Half Moon Bay State Beach", "Half Moon Bay / Coast", "California State Parks",
        37.4578, -122.4431, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/684", "https://www.parks.ca.gov/?page_id=531",
        52, "Tent, RV hookup & electric sites, hike-and-bike", "$35 - $65",
        6.5, 8.5, 8.5, 8, "May – Oct", "Nov – Feb (Mavericks season)",
        "Open year-round; huge winter swells at nearby Mavericks, brisk coastal walks on paved bluffs, heated coin showers.",
        "Right on the coastal bluffs above Francis Beach with crashing waves, beachcombing, and paved biking on the Coastside Trail.",
        "Coastside Trail (paved bluff path), Mavericks surf break, Pillar Point Harbor, Purisima Creek"
    ),
    make_cg(
        "memorial_park", "Memorial Park Campground", "Memorial County Park", "Peninsula / Santa Cruz Mtns", "San Mateo County Parks",
        37.2741, -122.2891, "Paid Reservation", "180 days (6 months) in advance on San Mateo County Parks reservation system",
        "https://www.smcgov.org/parks/reservations", "https://www.smcgov.org/parks/memorial-park",
        158, "Tent and RV sites along Pescadero Creek under tall redwoods", "$35 - $45",
        8.0, 8.0, 8.0, 7, "May – Sep", "Nov – Mar (Quiet creekside)",
        "Open year-round; high winter creek levels, cool damp redwood forest, very quiet and atmospheric.",
        "Beloved century-old park surrounded by towering coast redwoods and swimming holes in Pescadero Creek.",
        "Pescadero Creek swimming holes, Mount Ellen Trail, Pomponio Creek, Pescadero Marsh"
    ),
    make_cg(
        "butano_sp", "Butano State Park (Ben Ries Campground)", "Butano State Park", "Coast / Santa Cruz Mtns", "California State Parks",
        37.2023, -122.3392, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/681", "https://www.parks.ca.gov/?page_id=536",
        39, "Drive-in tent sites, walk-in sites, backpack trail camp", "$35",
        8.5, 8.5, 7.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; secluded redwood canyon cloaked in coastal fog and moss, tucked away near Pescadero.",
        "A quiet, lush redwood canyon sanctuary. Excellent trails through deep fern groves and sandstone ridgetops.",
        "Ano Nuevo State Park (elephant seals), Candelabra Tree, Goat Hill Trail, Jackson Flats"
    ),
    make_cg(
        "portola_redwoods", "Portola Redwoods State Park", "Portola Redwoods State Park", "Peninsula / Santa Cruz Mtns", "California State Parks",
        37.2536, -122.2181, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/680", "https://www.parks.ca.gov/?page_id=539",
        53, "Standard drive-in, walk-in, and backpack camp", "$35",
        9.0, 8.5, 7.0, 7, "May – Oct", "Nov – Mar",
        "Open year-round; deep quiet canyon with winter creek cascades and lush moss.",
        "Deep, quiet, rugged redwood canyon with giant trees, ferns, and one of the finest ancient groves in the Bay Area.",
        "Peters Creek Old Growth Grove, Tip Toe Falls, Slate Creek Trail, Iverson Trail"
    ),
    make_cg(
        "sanborn_county_park", "Sanborn County Park", "Sanborn County Park", "Santa Cruz Mountains", "Santa Clara County Parks",
        37.2347, -122.0622, "Paid Reservation", "6 months rolling on Santa Clara County Parks portal",
        "https://gooutsideandplay.org/", "https://parks.sccgov.org/santa-clara-county-parks/sanborn-county-park",
        33, "Walk-in tent campsites tucked under coastal redwoods", "$28",
        8.5, 8.0, 7.0, 6, "May – Oct", "Nov – Mar",
        "Open year-round; mild redwood climate, fast access from South Bay.",
        "Lush redwood forest tucked onto the eastern slope of the Santa Cruz Mountains above Saratoga. Direct trail link to Castle Rock.",
        "Skyline Trail, Castle Rock State Park sandstone climbing spires, Sanborn Creek trail, Indian Rock"
    ),
    make_cg(
        "big_basin_sempervirens", "Big Basin: Sempervirens Campground", "Big Basin Redwoods State Park", "Santa Cruz Mountains", "California State Parks",
        37.1723, -122.2218, "Paid Reservation", "60-day rolling window on ReserveCalifornia (limited reopening post-CZU fire)",
        "https://www.reservecalifornia.com/Web/#!park/691", "https://www.parks.ca.gov/?page_id=540",
        30, "Drive-in & walk-in tent sites along Sempervirens Creek", "$35",
        9.5, 9.0, 6.5, 8, "Apr – Oct", "Nov – Mar",
        "Open year-round (rebuilding); winter rain feeds Berry Creek and Sempervirens waterfalls, vivid green redwood rebirth.",
        "California's oldest state park (1902). Resilient ancient redwoods rebounding with vibrant green sprouts.",
        "Redwood Loop, Berry Creek Falls trail reconstruction, Skyline-to-the-Sea trail, Waddell Creek"
    ),
    make_cg(
        "big_basin_blooms", "Big Basin: Blooms Creek Campground", "Big Basin Redwoods State Park", "Santa Cruz Mountains", "California State Parks",
        37.1685, -122.2152, "Paid Reservation", "60-day rolling window on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/691", "https://www.parks.ca.gov/?page_id=540",
        15, "Drive-in campsites shaded by surviving ancient redwood sentinels", "$35",
        9.0, 8.5, 6.0, 8, "Apr – Oct", "Nov – Mar",
        "Open year-round with seasonal reopening schedule; peaceful redwood creekside setting.",
        "Located in the upper Blooms Creek basin surrounded by resilient coast redwoods.",
        "Blooms Creek Trail, Pine Mountain, Opal Creek, Gazos Creek"
    ),
    make_cg(
        "henry_cowell", "Henry Cowell Redwoods State Park", "Henry Cowell Redwoods State Park", "Santa Cruz Mountains", "California State Parks",
        37.0426, -122.0583, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/701", "https://www.parks.ca.gov/?page_id=546",
        107, "Drive-in tent, RV (no hookups) in pine and oak ridge", "$35",
        8.5, 8.5, 8.0, 8, "May – Sep", "Nov – Mar",
        "Open year-round; river levels rise in winter; majestic old-growth loop trail.",
        "Ancient 275-foot redwoods, sandy pine ridges, and freshwater river swimming in the San Lorenzo River.",
        "Old Growth Redwood Grove, Garden of Eden swimming hole, Roaring Camp steam train, Fall Creek unit"
    ),
    make_cg(
        "new_brighton", "New Brighton State Beach", "New Brighton State Beach", "Monterey Bay Coast", "California State Parks",
        36.9806, -121.9312, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/700", "https://www.parks.ca.gov/?page_id=542",
        111, "Beach bluff tent & RV sites (premium oceanfront hookups)", "$35 - $60",
        6.5, 8.5, 9.0, 9, "May – Oct", "Nov – Feb",
        "Open year-round; coastal bluff camping overlooking the entire crescent of Monterey Bay.",
        "Forested bluff campsites looking out across Monterey Bay; dolphins and otters often visible directly from camp.",
        "Capitola Village, Forest of Nisene Marks State Park, Monterey Bay coastal bluff trails"
    ),
    make_cg(
        "mt_madonna", "Mount Madonna County Park (Campground & Yurts)", "Mount Madonna County Park", "Santa Cruz Mountains", "Santa Clara County Parks",
        37.0108, -121.7067, "Paid Reservation", "6 months in advance on Santa Clara County Parks portal",
        "https://gooutsideandplay.org/", "https://parks.sccgov.org/santa-clara-county-parks/mt-madonna-county-park",
        118, "Drive-in tent, RV sites, and 5 rustic canvas yurts", "$30 - $45 ($85 yurts)",
        8.0, 8.5, 7.5, 6, "May – Oct", "Nov – Mar",
        "Open year-round; canvas yurts provide heated winter glamping under the redwoods.",
        "Majestic coast redwood forest perched atop the Santa Cruz mountain ridge between Gilroy and Watsonville.",
        "Henry Miller historic estate ruins, giant redwood groves, white fallow deer sanctuary, Mt. Madonna archery range"
    ),
    make_cg(
        "uvas_canyon", "Uvas Canyon County Park", "Uvas Canyon County Park", "South Bay / Santa Cruz Mtns", "Santa Clara County Parks",
        37.0864, -121.7925, "Paid Reservation", "6 months in advance on Santa Clara County Parks portal",
        "https://gooutsideandplay.org/", "https://parks.sccgov.org/santa-clara-county-parks/uvas-canyon-county-park",
        25, "Drive-in tent campsites nestled along Swanson Creek", "$32",
        8.5, 8.5, 7.5, 7, "May – Oct", "Nov – Mar (Winter waterfall season!)",
        "Open year-round; winter and spring are the premier seasons as winter rains turn all six canyon waterfalls into roaring cascades.",
        "Lush canyon wonderland packed with six multi-tiered natural waterfalls cascading through mossy ferns and Douglas firs.",
        "Waterfall Loop Trail (Black Rock Falls, Basin Falls, Upper Falls), Swanson Creek, Alec Canyon Trail"
    ),

    # -------------------------------------------------------------
    # 7. SONOMA, NAPA VALLEY & NORTH BAY LAKES
    # -------------------------------------------------------------
    make_cg(
        "sugarloaf_ridge", "Sugarloaf Ridge State Park", "Sugarloaf Ridge State Park", "Sonoma / Napa", "California State Parks / Sonoma Ecology Ctr",
        38.4379, -122.5137, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/696", "https://sugarloafpark.org/",
        47, "Drive-in tent, small RV, plus luxury glamping tents", "$35 ($120 glamping)",
        9.0, 9.0, 8.0, 7, "May – Oct", "Nov – Mar",
        "Open year-round; dark skies for astronomy; winter creek waterfalls flow vigorously.",
        "Sonoma Valley gem with dark skies, public observatory stargazing, waterfalls, and steep panoramic climbs.",
        "Bald Mountain summit (view Sierra & SF on clear days), Sonoma Creek Falls, Ferguson Observatory"
    ),
    make_cg(
        "bothe_napa", "Bothe-Napa Valley State Park", "Bothe-Napa Valley State Park", "Sonoma / Napa", "California State Parks / Napa County Reg Parks",
        38.5368, -122.5298, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/706", "https://napaoutdoors.org/parks/bothe-napa-valley-state-park/",
        50, "Drive-in tent, RV, historic cabins & yurts", "$35 ($75 yurts)",
        8.0, 8.0, 8.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; historic restored cabins provide cozy winter stays in wine country.",
        "Camp nestled among redwoods and maple in the heart of Napa wine country; spring-fed swimming pool in summer.",
        "Ritchey Creek Trail, Coyote Peak, Bale Grist Mill State Historic Park, Napa Valley Vine Trail"
    ),
    make_cg(
        "lake_berryessa", "Lake Berryessa (Pleasure Cove Marina)", "Lake Berryessa Recreation Area", "Sonoma / Napa", "Bureau of Reclamation / Sun Outdoors",
        38.5083, -122.2356, "Paid Reservation", "Rolling advance reservations on Pleasure Cove portal",
        "https://www.sunoutdoors.com/california/pleasure-cove-marina", "https://www.usbr.gov/mp/ccao/berryessa/",
        140, "Lakeside tent, full-hookup RV sites, and rustic cabins", "$35 - $65",
        6.5, 8.0, 8.0, 6, "Jun – Aug", "Nov – Mar",
        "Open year-round; pleasant mild winter weather, quiet lake views.",
        "Expansive warm-water reservoir nestled in eastern Napa County hills with full-service marina and lakefront tenting.",
        "Monticello Dam Glory Hole spillway, Smittle Creek Trail, swimming coves, boat wakeboarding"
    ),
    make_cg(
        "austin_creek", "Austin Creek SRA (Bullfrog Pond)", "Austin Creek State Recreation Area", "Sonoma / Russian River", "California State Parks / Stewards of Coast & Redwoods",
        38.5447, -123.0189, "Paid Reservation", "Rolling on Hipcamp / Stewards of Coast & Redwoods portal",
        "https://www.hipcamp.com/en-US/land/california-bullfrog-pond-campground-austin-creek-sra-98xh1z11", "https://www.parks.ca.gov/?page_id=452",
        24, "Drive-in primitive tent & backpack trail camps", "$35",
        8.5, 8.5, 5.0, 6, "May – Oct", "Nov – Mar",
        "Open year-round; high elevation ridge camp above Guerneville fog layer.",
        "Perched high above Guerneville and Armstrong Redwoods; rugged oak savanna, rolling ridges, and serene starry skies.",
        "Armstrong Redwoods State Natural Reserve, Gilliam Creek, East Ridge Trail, Russian River paddling"
    ),
    make_cg(
        "lake_sonoma", "Lake Sonoma Recreation Area", "Lake Sonoma Recreation Area", "Sonoma / Russian River", "US Army Corps of Engineers",
        38.7183, -122.9981, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233596", "https://www.spn.usace.army.mil/Missions/Recreation/Lake-Sonoma/",
        115, "Drive-in campsites at Warm Springs + 15 primitive Boat-In/Hike-In wilderness camps", "$20 - $35",
        7.5, 8.0, 7.5, 6, "May – Sep", "Nov – Mar",
        "Open year-round; boat-in camping along 50 miles of winding shoreline.",
        "Warm water lake tucked into Sonoma hills; unique boat-in boat camping along 50 miles of winding shoreline.",
        "Lake Sonoma Marina, Little Flat trail, Warm Springs Dam, Dry Creek Valley wineries"
    ),
    make_cg(
        "clear_lake_kelsey", "Clear Lake: Kelsey Creek Campground", "Clear Lake State Park", "Lake County / North Bay", "California State Parks",
        39.0142, -122.8156, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/457", "https://www.parks.ca.gov/?page_id=473",
        65, "Drive-in tent and RV sites along creek channel with boat launch", "$35",
        8.0, 8.5, 7.5, 6, "May – Sep", "Nov – Mar",
        "Open year-round; world-class bass fishing during winter and spring months.",
        "Situated on the quiet shores of California's oldest natural freshwater lake under the volcanic shadow of Mount Konocti.",
        "Mount Konocti dormant volcano summit hike (Wright Peak 4,299 ft), Kelsey Creek nature trail, bass fishing"
    ),
    make_cg(
        "clear_lake_cole", "Clear Lake: Cole Creek Campground", "Clear Lake State Park", "Lake County / North Bay", "California State Parks",
        39.0185, -122.8192, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/457", "https://www.parks.ca.gov/?page_id=473",
        82, "Drive-in tent and RV sites in shaded oak woodland near swim beach", "$35",
        7.5, 8.0, 7.5, 6, "May – Sep", "Nov – Mar",
        "Open year-round; shaded camping near swimming beach and boat marina.",
        "Wooded campsites under oak canopy with easy walking access to the sandy swimming beach.",
        "Cole Creek trail, swim beach, kayak rentals, Mount Konocti views"
    ),

    # -------------------------------------------------------------
    # 8. SONOMA & MENDOCINO COAST
    # -------------------------------------------------------------
    make_cg(
        "sonoma_coast_wrights", "Sonoma Coast: Wright's Beach Campground", "Sonoma Coast State Park", "Sonoma / Coast", "California State Parks",
        38.3992, -123.0975, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia (sells out in seconds)",
        "https://www.reservecalifornia.com/Web/#!park/451", "https://www.parks.ca.gov/?page_id=451",
        27, "Beachfront drive-in campsites steps from crashing Pacific surf", "$45",
        9.0, 10.0, 7.0, 10, "May – Oct (Sold out instantly)", "Nov – Mar (Winter storm watching)",
        "Open year-round; watch thundering Pacific winter breakers crash right in front of your campfire.",
        "Step directly from your campsite onto the sand. The most coveted oceanfront drive-in campsites in Northern California.",
        "Kortum Trail (bluff hike to Blind Beach), Duncan's Landing, Goat Rock seal colony"
    ),
    make_cg(
        "sonoma_coast_bodega", "Sonoma Coast: Bodega Dunes Campground", "Sonoma Coast State Park", "Sonoma / Coast", "California State Parks",
        38.3533, -123.0567, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/451", "https://www.parks.ca.gov/?page_id=451",
        98, "Drive-in tent & RV sites sheltered behind tall coastal dunes with hot showers", "$35",
        8.0, 8.5, 8.0, 8, "May – Oct", "Nov – Mar",
        "Open year-round; sand dunes provide shelter from high winter coastal winds; coin-operated hot showers.",
        "Spacious campsites tucked behind coastal dunes with boardwalk paths leading directly out to expansive sandy beaches.",
        "Bodega Head whale watching, Salmon Creek surf break, Bodega Dunes trail"
    ),
    make_cg(
        "sonoma_coast_pomo", "Sonoma Coast: Pomo Canyon Environmental Camp", "Sonoma Coast State Park", "Sonoma / Coast", "California State Parks",
        38.4312, -123.0642, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/451", "https://www.parks.ca.gov/?page_id=451",
        21, "Walk-in campsites in peaceful second-growth redwood canyon", "$25",
        9.0, 8.5, 4.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; sheltered inland redwood canyon, escape coastal wind while staying 2 miles from ocean.",
        "A hidden redwood sanctuary tucked into the hills just behind the coastal bluffs. Direct access to the Pomo Canyon Trail.",
        "Pomo Canyon Trail to Shell Beach, Red Hill Trail, Russian River mouth"
    ),
    make_cg(
        "salt_point_gerstle", "Salt Point: Gerstle Cove Campground", "Salt Point State Park", "Sonoma / Coast", "California State Parks",
        38.5663, -123.3294, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/693", "https://www.parks.ca.gov/?page_id=453",
        30, "Drive-in ocean bluff sites just above Gerstle Cove marine reserve", "$35",
        9.5, 9.5, 7.0, 9, "May – Oct", "Nov – Mar",
        "Open year-round; ocean bluff perch with crashing winter waves, tide pools, and crisp sunset views.",
        "Perched on open coastal bluffs above Gerstle Cove Marine Reserve. World-class abalone and scuba diving location.",
        "Tafoni sandstone formations, Gerstle Cove Marine Reserve, Salt Point bluff trail"
    ),
    make_cg(
        "salt_point_woodside", "Salt Point: Woodside Campground", "Salt Point State Park", "Sonoma / Coast", "California State Parks",
        38.5722, -123.3217, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/693", "https://www.parks.ca.gov/?page_id=453",
        79, "Drive-in forest sites tucked among bishop pines and huckleberry", "$35",
        9.0, 8.5, 7.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; densely forested setting provides wind shelter during coastal storms.",
        "Located on the east side of Highway 1 nestled in a dense bishop pine and rhododendron forest with trail to Pygmy Forest.",
        "Pygmy Forest Trail, Central Trail to ocean bluffs, Fisk Mill Cove"
    ),
    make_cg(
        "hendy_woods", "Hendy Woods State Park (Campground & Cabins)", "Hendy Woods State Park", "Mendocino / Anderson Valley", "California State Parks",
        39.0722, -123.4731, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/438", "https://www.parks.ca.gov/?page_id=438",
        92, "Drive-in tent & RV sites, plus 4 rustic Azalea cabins", "$35 ($75 cabins)",
        8.5, 8.5, 8.0, 7, "May – Oct", "Nov – Mar",
        "Open year-round; rustic cabins offer heating for cozy winter redwood stays.",
        "Less crowded old-growth redwood sanctuary in Anderson Valley along the gentle Navarro River.",
        "Big Hendy Old Growth Redwood Grove (1,000-year-old trees), Navarro River swimming, Anderson Valley Pinot Noir"
    ),
    make_cg(
        "russian_gulch", "Russian Gulch State Park Campground", "Russian Gulch State Park", "Mendocino Coast", "California State Parks",
        39.3292, -123.8056, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/432", "https://www.parks.ca.gov/?page_id=432",
        30, "Standard drive-in campsites in lush fern-draped canyon", "$35",
        9.5, 9.5, 7.5, 9, "May – Oct", "Nov – Mar",
        "Open year-round; winter rains transform Russian Gulch Falls into a roaring cascade; dramatic sea waves at Devil's Punchbowl.",
        "Mendocino coastal paradise: towering sea-bridge, dramatic blowholes, lush fern canyons, and ocean headlands.",
        "Devil's Punchbowl sea chasm, Russian Gulch 36-ft Waterfall Trail, Frederick W. Panhorst Bridge, coastal headlands"
    ),
    make_cg(
        "van_damme", "Van Damme State Park Campground", "Van Damme State Park", "Mendocino Coast", "California State Parks",
        39.2742, -123.7892, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/433", "https://www.parks.ca.gov/?page_id=433",
        74, "Drive-in and walk-in campsites in Little River redwood canyon", "$35",
        9.0, 9.0, 7.5, 8, "May – Oct", "Nov – Mar",
        "Open year-round; sheltered canyon camping near sea caves and Pygmy forest.",
        "Campsites along Little River in a sheltered canyon; kayak tours into sea caves launch directly from the park's beach.",
        "Fern Canyon Trail, Pygmy Forest boardwalk, sea kayaking in Van Damme cove"
    ),

    # -------------------------------------------------------------
    # 9. MONTEREY BAY, SALINAS & BIG SUR
    # -------------------------------------------------------------
    make_cg(
        "fremont_peak_oak", "Fremont Peak: Oak Point Campground", "Fremont Peak State Park", "Monterey Bay & Salinas", "California State Parks",
        36.7601, -121.5036, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/713", "https://www.parks.ca.gov/?page_id=564",
        12, "Primitive drive-in & tent sites tucked under valley oaks", "$25",
        8.5, 9.0, 5.0, 5, "Apr – Oct", "Nov – Feb (Crisp winter star viewing)",
        "Open year-round; high ridge winds and occasional light snow dustings at 3,169 ft. Crystal-clear winter skies for astronomy.",
        "Sheltered camping under coastal oaks just below the summit of Fremont Peak. Direct trail to astronomical observatory.",
        "Fremont Peak Trail to 3,169-ft summit, Fremont Peak Astronomical Observatory, San Juan Bautista historic mission"
    ),
    make_cg(
        "fremont_peak_valley", "Fremont Peak: Valley View Campground", "Fremont Peak State Park", "Monterey Bay & Salinas", "California State Parks",
        36.7618, -121.5052, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/713", "https://www.parks.ca.gov/?page_id=564",
        13, "Primitive ridge campsites with expansive valley and ocean sunset views", "$30",
        8.5, 9.5, 5.0, 6, "Apr – Oct", "Nov – Feb",
        "Open year-round; unobstructed sunset views across the Salinas Valley out to Monterey Bay.",
        "High ridge camping with sweeping 360-degree vistas across Monterey Bay and Salinas Valley. World-renowned dark sky astronomy.",
        "Summit Trail, Valley View Trail, dark sky stargazing"
    ),
    make_cg(
        "pfeiffer_big_sur", "Pfeiffer Big Sur State Park", "Pfeiffer Big Sur State Park", "Monterey Bay & Big Sur", "California State Parks",
        36.2486, -121.7825, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia (very high demand)",
        "https://www.reservecalifornia.com/Web/#!park/720", "https://www.parks.ca.gov/?page_id=570",
        189, "Drive-in tent, RV (no hookups), walk-in riverside sites", "$35 - $50",
        10.0, 10.0, 8.0, 10, "May – Oct (Sold out 6 mos ahead)", "Nov – Mar (Off-season serene Big Sur)",
        "Open year-round; winter rains awaken Pfeiffer Falls, rushing Big Sur River, cozy campfire evenings.",
        "The quintessential Big Sur experience along the redwood-canopied Big Sur River with natural river swimming holes.",
        "Buzzard's Roost Trail, Big Sur River Gorge, Pfeiffer Falls, Valley View Trail, Pfeiffer Beach purple sands"
    ),
    make_cg(
        "julia_pfeiffer_burns", "Julia Pfeiffer Burns State Park", "Julia Pfeiffer Burns State Park", "Monterey Bay & Big Sur", "California State Parks",
        36.1601, -121.6728, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia (only 2 walk-in sites!)",
        "https://www.reservecalifornia.com/Web/#!park/722", "https://www.parks.ca.gov/?page_id=578",
        2, "Environmental walk-in cliffside tent sites (Sites 1 & 2)", "$30",
        9.0, 10.0, 3.0, 10, "Year-Round (Only 2 sites on earth!)", "Winter (Spectacular sunsets)",
        "Open year-round; only two walk-in sites perched on the cliffs overlooking McWay Falls and turquoise Pacific cove. Sells out instantly.",
        "Legendary cliff-edge campsites perched directly over the Pacific near McWay Falls. Pure coastal magic.",
        "McWay Falls (80-ft waterfall into turquoise Pacific cove), Ewoldsen Trail, Partington Cove"
    ),
    make_cg(
        "kirk_creek", "Kirk Creek Campground", "Los Padres National Forest (Big Sur)", "Monterey Bay & Big Sur", "US Forest Service (Los Padres NF)",
        35.9897, -121.4939, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov + several First-Come First-Served sites",
        "https://www.recreation.gov/camping/campgrounds/233116", "https://www.fs.usda.gov/recarea/lpnf/recarea/?recid=10910",
        33, "Drive-in bluff tent & RV sites directly overlooking Pacific Ocean", "$45",
        9.5, 10.0, 5.0, 9, "Apr – Oct", "Nov – Mar",
        "Open year-round; dramatic open bluff ocean views, whale watching with binoculars from your tent.",
        "Every campsite has an unobstructed, panoramic view of the Pacific Ocean from an open coastal bluff.",
        "Vicente Flat Trail (into Ventana Wilderness), Sand Dollar Beach, Mill Creek cove"
    ),
    make_cg(
        "plaskett_creek", "Plaskett Creek Campground", "Los Padres National Forest (Big Sur)", "Monterey Bay & Big Sur", "US Forest Service (Los Padres NF)",
        35.9189, -121.4683, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233117", "https://www.fs.usda.gov/recarea/lpnf/recarea/?recid=10911",
        44, "Drive-in tent & RV sites in Monterey pine grove", "$45",
        8.5, 9.0, 7.5, 8, "Apr – Oct", "Nov – Mar",
        "Open year-round; grassy park-like sites sheltered by tall pines, steps from Sand Dollar Beach.",
        "Park-like grassy setting under giant Monterey pines just across Highway 1 from Sand Dollar Beach.",
        "Sand Dollar Beach (largest sandy beach in Big Sur), Jade Cove, Willow Creek"
    ),
    make_cg(
        "prewitt_ridge", "Prewitt Ridge Dispersed Area", "Ventana Wilderness / Los Padres NF", "Monterey Bay & Big Sur", "US Forest Service / BLM",
        35.9708, -121.4475, "Dispersed / Free FCFS", "No reservations - 100% Free Dispersed Camping (High clearance AWD/4WD recommended, bring all water)",
        "https://www.fs.usda.gov/recarea/lpnf/recarea/?recid=10903", "https://www.fs.usda.gov/recarea/lpnf/recarea/?recid=10903",
        25, "Primitive dispersed rim campsites at 3,200 ft elevation", "Free ($0)",
        8.5, 10.0, 1.5, 6, "May – Oct", "Nov – Apr (Mud makes road impassable)",
        "Primitive dirt road (Nacimiento-Fergusson / Coast Ridge Rd). 4WD required, highly impassable when muddy in winter. Zero water.",
        "High-altitude coastal ridge camping 3,200 feet directly above the Pacific Ocean. Sleep above the clouds with jaw-dropping sunsets.",
        "Prewitt Loop Trail, Ventana Wilderness, 3,200-ft cliff drop overlooking marine fog bank"
    ),
    make_cg(
        "pinnacles_np", "Pinnacles National Park Campground", "Pinnacles National Park", "Central Coast / Pinnacles", "National Park Service",
        36.4886, -121.1444, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/234015", "https://www.nps.gov/pinn/planyourvisit/camp.htm",
        134, "Tent, RV with electrical hookups, tent cabins, group sites", "$40 - $55",
        9.0, 9.0, 7.0, 7, "Feb – May (Spring flowers & mild temps)", "Jun – Aug (Extreme 105°F heat)",
        "Open year-round; winter is prime season! Mild hiking weather in the 60s, lush moss in Bear Gulch Caves, active condor flights.",
        "Only campground in California's newest National Park; home to soaring California Condors, talus caves, and swimming pool.",
        "High Peaks Trail (carved rock steps into volcanic spires), Bear Gulch Cave (talus cave), Condor viewing"
    ),
    make_cg(
        "san_luis_basalt", "San Luis Reservoir: Basalt Campground", "San Luis Reservoir State Rec Area", "Central Valley / Pacheco Pass", "California State Parks",
        37.0542, -121.0567, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/733", "https://www.parks.ca.gov/?page_id=558",
        79, "Drive-in tent and RV sites in sheltered basalt canyon", "$30 - $40",
        7.0, 7.5, 7.5, 4, "Mar – May", "Jun – Aug (Very hot)",
        "Open year-round; mild winter and spring camping with rolling green hills and spring wildflowers.",
        "Sheltered basalt canyon below massive San Luis Dam near Pacheco Pass; gateway to warm central valley water sports and rolling hills.",
        "Basalt Hill Trail, Pacheco Pass historic stagecoach trail, spring wildflower hillsides, reservoir boating"
    ),
    make_cg(
        "san_luis_creek", "San Luis Reservoir: San Luis Creek Camp", "San Luis Reservoir State Rec Area", "Central Valley / Pacheco Pass", "California State Parks",
        37.0912, -121.0185, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/733", "https://www.parks.ca.gov/?page_id=558",
        53, "Waterfront campsites on O'Neill Forebay with boat launch", "$35",
        6.5, 7.5, 8.0, 4, "Apr – Sep", "Nov – Mar",
        "Open year-round; lakefront recreation on O'Neill Forebay.",
        "Direct water access on the O'Neill Forebay with windsurfing, boat launching, and swimming beach.",
        "O'Neill Forebay water sports, striped bass fishing, shoreline trail"
    ),
    make_cg(
        "brannan_island", "Brannan Island State Recreation Area", "Brannan Island State Recreation Area", "Delta / Central Valley", "California State Parks",
        38.1172, -121.6967, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/736", "https://www.parks.ca.gov/?page_id=487",
        102, "Drive-in tent and RV sites, boat launch, group sites", "$30 - $45",
        6.5, 7.5, 7.5, 5, "May – Sep", "Nov – Mar",
        "Open year-round; mild delta winter weather, world-class striped bass & sturgeon fishing.",
        "Island paradise in the maze of the Delta. Ideal basecamp for kayak exploring, sailing, and warm delta river breezes.",
        "Sacramento-San Joaquin Delta sloughs, windy kayak trails, striped bass & sturgeon fishing, windsurfing on Sherman Island"
    ),

    # -------------------------------------------------------------
    # 10. LAKE TAHOE BASIN (WINTER & SUMMER INTELLIGENCE)
    # -------------------------------------------------------------
    make_cg(
        "sugar_pine_point", "Sugar Pine Point: General Creek Campground", "Sugar Pine Point State Park", "Lake Tahoe Basin", "California State Parks",
        39.0578, -120.1242, "Paid Reservation (Year-Round)", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/678", "https://www.parks.ca.gov/?page_id=510",
        175, "Drive-in tent & RV sites (Plowed loops in winter with heated modern restrooms!)", "$35",
        9.5, 9.5, 9.0, 8, "Jul – Aug (Summer) & Jan – Feb (Winter snow camping)", "Apr – May & Oct – Nov",
        "THE WINTER CROWN JEWEL: One of the only campgrounds in Lake Tahoe open all winter for official plowed snow camping! Heated modern restrooms with flush toilets and hot running water. Directly adjacent to 12+ miles of marked/groomed Nordic ski and snowshoe trails along General Creek (1960 Winter Olympic Nordic site).",
        "Lake Tahoe's premier year-round state park. In winter, camp in deep powder snow with heated restrooms; in summer, enjoy quiet sandy beaches beneath towering 200-foot sugar pines.",
        "General Creek Trail, D.L. Bliss / Rubicon Trail connection, Ehrman Mansion, Olympic 1960 Nordic trails, Sugar Pine beach"
    ),
    make_cg(
        "donner_memorial_sp", "Donner Memorial State Park (Donner Lake)", "Donner Memorial State Park", "Lake Tahoe Basin", "California State Parks",
        39.3183, -120.2361, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/704", "https://www.parks.ca.gov/?page_id=503",
        154, "Drive-in tent & RV sites, split among 3 wooded loops", "$35",
        8.5, 9.0, 8.5, 7, "Jun – Aug (Lake swimming) & Dec – Mar (Winter snow sports)", "May & Sep – Oct",
        "Vehicle campground closed Nov–Apr, but park grounds remain fully open for groomed cross-country ski trails, snowshoe rentals, and heated visitor museum. 15 minutes to Palisades Tahoe, Alpine Meadows, Sugar Bowl, and Northstar.",
        "Steeped in pioneer history along the shores of Donner Lake in Truckee. Perfect summer alpine basecamp, and a premier winter snowshoeing destination.",
        "Donner Summit Canyon Trail, Pacific Crest Trail (Donner Pass), Historic China Wall, Emigrant Trail Museum, Truckee River"
    ),
    make_cg(
        "william_kent", "William Kent Campground (North Lake Tahoe)", "Lake Tahoe Basin Management Unit", "Lake Tahoe Basin", "US Forest Service (Lake Tahoe Basin MU)",
        39.1417, -120.1583, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232770", "https://www.fs.usda.gov/recarea/ltbmu/recarea/?recid=11786",
        81, "Drive-in tent, RV sites (some electric hookups), yurt sites", "$36 - $50",
        8.5, 9.0, 8.0, 8, "Jul – Aug (Peak North Lake Tahoe beach season)", "May – Jun & Sep – Oct",
        "Closed for vehicle camping in winter. Serves as a prime access point: 10 minutes to Palisades Tahoe, 5 minutes to Tahoe City Winter Sports Park (groomed XC skiing, ice skating).",
        "The best-located federal campground on North Lake Tahoe. Minutes from Tahoe City's cafes and lakeside pathways, with beach access across the street.",
        "Tahoe Rim Trail (Ward Creek trailhead), Stanford Rock trail, Page Meadows mountain biking, Tahoe City marina"
    ),
    make_cg(
        "meeks_bay", "Meeks Bay Campground & Resort", "Lake Tahoe Basin Management Unit", "Lake Tahoe Basin", "US Forest Service / Washoe Tribe",
        39.0347, -120.1256, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov (extremely coveted)",
        "https://www.recreation.gov/camping/campgrounds/232840", "https://www.meeksbayresort.com/",
        40, "Tent and RV campsites steps from shoreline", "$38",
        9.0, 10.0, 7.5, 9, "Jun – Sep (Sells out in minutes)", "Late May & late Sep",
        "Vehicle campground closed Nov–Apr under feet of snow. Serves as winter backcountry departure point for snowshoers entering the snowbound Meeks Creek valley into Desolation Wilderness.",
        "Widely acclaimed as the prettiest beach setting on Lake Tahoe. Golden sand, crystal azure water, and direct trailhead into the granite heart of Desolation Wilderness.",
        "Meeks Creek Trail (into northern Desolation Wilderness & Rubicon Lake), Rubicon Trail, Sugar Pine Point"
    ),
    make_cg(
        "kaspian_camp", "Kaspian Campground (Tent-Only / West Shore)", "Lake Tahoe Basin Management Unit", "Lake Tahoe Basin", "US Forest Service (Lake Tahoe Basin MU)",
        39.1128, -120.1558, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232839", "https://www.fs.usda.gov/recarea/ltbmu/recarea/?recid=11776",
        9, "Intimate tent-only campsites nestled in Jeffrey pines across from lake", "$24",
        9.0, 9.0, 6.0, 7, "Jul – Aug", "Late Spring & Fall",
        "Campground closed in winter, but directly adjacent to Blackwood Canyon Sno-Park for winter backcountry staging.",
        "Intimate 9-site tent-only campground directly across Highway 89 from Lake Tahoe with direct paved bicycle trail.",
        "Blackwood Canyon, Barker Pass (PCT), Ellis Peak, Eagle Rock volcanic vista hike"
    ),
    make_cg(
        "blackwood_snopark", "Blackwood Canyon Sno-Park Staging Camp", "Lake Tahoe Basin Management Unit", "Lake Tahoe Basin", "California State Parks / USFS",
        39.1135, -120.1585, "Sno-Park Permit Required (Winter)", "CA Sno-Park Permit ($15 day / $40 season) Nov 1 to May 30",
        "https://ohv.parks.ca.gov/?page_id=1233", "https://ohv.parks.ca.gov/?page_id=1233",
        20, "Plowed winter staging area for backcountry ski touring, snowmobiling & snowshoeing", "$15 permit",
        9.5, 9.5, 3.0, 6, "Dec – Mar (Peak winter snowpack)", "Summer (Paved staging)",
        "NORTH TAHOE WINTER EPICENTER: Plowed parking staging area for snowmobiling up Blackwood Canyon to Barker Pass (PCT), backcountry ski touring to Ellis Peak (8,740 ft), and snowshoeing along Blackwood Creek. Requires California Sno-Park permit.",
        "Winter backcountry departure hub for North Lake Tahoe's most expansive alpine terrain.",
        "Barker Pass, Ellis Peak (8,740 ft), Pacific Crest Trail winter route, Blackwood Creek"
    ),
    make_cg(
        "eagle_point_tahoe", "Emerald Bay: Eagle Point Campground", "Emerald Bay State Park", "Lake Tahoe Basin", "California State Parks",
        38.9512, -120.0985, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/676", "https://www.parks.ca.gov/?page_id=506",
        100, "Drive-in tent & RV sites on forested bluff overlooking Emerald Bay", "$35 - $45",
        10.0, 10.0, 7.5, 9, "Jun – Sep", "Oct & May",
        "Closed Nov–Apr due to heavy snow and cliffside road conditions. World-famous viewpoint above Fannette Island.",
        "Perched on the forested granite cliffs looking directly down into the azure waters of Emerald Bay and Fannette Island.",
        "Rubicon Trail, Vikingsholm Castle, Eagle Falls, Emerald Bay Lookout"
    ),
    make_cg(
        "emerald_bay_boatin", "Emerald Bay: Boat-In Campground", "Emerald Bay State Park", "Lake Tahoe Basin", "California State Parks",
        38.9612, -120.1035, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/676", "https://www.parks.ca.gov/?page_id=506",
        22, "Lake-access boat-in campsites on northern shore of Emerald Bay", "$35",
        9.5, 10.0, 5.0, 9, "Jun – Sep", "Closed in winter",
        "Accessible only by boat or kayak across Emerald Bay or by hiking in from D.L. Bliss.",
        "Spectacular boat-in camping situated right on the quiet northern shoreline of Emerald Bay near the mouth of the bay.",
        "Emerald Bay paddle routes, Fannette Island tea house ruins, Rubicon Point"
    ),
    make_cg(
        "dl_bliss", "D.L. Bliss State Park Campground", "D.L. Bliss State Park", "Lake Tahoe Basin", "California State Parks",
        38.9785, -120.0995, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/676", "https://www.parks.ca.gov/?page_id=505",
        150, "Drive-in campsites tucked among giant granite boulders near lake", "$35 - $45",
        10.0, 10.0, 8.0, 9, "Jun – Sep", "Closed in winter",
        "Closed in winter under 6 to 10 feet of snow.",
        "Home to Calawee Cove beach—one of Lake Tahoe's most beautiful hidden boulder coves. Starting point of the cliffside Rubicon Trail.",
        "Rubicon Trail, Calawee Cove beach, Balancing Rock trail, Lester Beach"
    ),
    make_cg(
        "spooner_lake", "Spooner Lake & Sand Harbor Camps", "Lake Tahoe-Nevada State Park", "Lake Tahoe Basin", "Nevada State Parks",
        39.1067, -119.9042, "Paid Reservation", "11 months rolling on ReserveAmerica / Nevada State Parks",
        "https://www.reserveamerica.com/explore/spooner-lake-and-marlette-flume-state-park/NV/1000000/overview", "https://parks.nv.gov/parks/lake-tahoe-nevada-state-park",
        15, "Rustic wilderness cabins & walk-in campsites at Spooner Lake", "$25 ($85 cabins)",
        9.5, 10.0, 7.0, 8, "Jul – Aug & Jan – Feb (Winter XC skiing)", "May – Jun & Sep – Oct",
        "Spooner Lake transforms into a winter wonderland with over 12 km of groomed cross-country ski and snowshoe trails winding through quiet aspen groves and pine forests.",
        "On the scenic East/North Shore of Lake Tahoe. Spooner Lake offers tranquil high-elevation forest camping and winter Nordic trails, with quick access to the Caribbean-blue waters of Sand Harbor.",
        "Flume Trail, Marlette Lake, Tahoe Rim Trail, Sand Harbor crystal waters"
    ),

    # -------------------------------------------------------------
    # 11. SIERRA NATIONAL WILDERNESS AREAS
    # -------------------------------------------------------------
    make_cg(
        "desolation_bayview", "Desolation Wilderness: Bayview Camp", "Desolation Wilderness", "Sierra Wilderness Areas", "US Forest Service (Eldorado NF)",
        38.9486, -120.0883, "First-Come, First-Served", "100% First-Come, First-Served trailhead camping ($20). Wilderness permits on Rec.gov.",
        "https://www.recreation.gov/permits/233261", "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78424",
        12, "Trailhead tent campsites directly at Bayview / Desolation trailhead", "$20",
        10.0, 10.0, 3.0, 8, "Jul – Sep (Alpine hiking)", "Oct & Jun",
        "EXTREME ALPINE WINTER WILDERNESS: Buried under 10–25 feet of snow in winter. Staging area for mountaineers climbing Mount Tallac (9,735 ft).",
        "Trailhead campground perched directly on the granite ridge above Emerald Bay. Gateway into Desolation Wilderness.",
        "Mount Tallac summit (panoramic view of all Lake Tahoe), Granite Lake, Maggie's Peaks, Desolation Wilderness"
    ),
    make_cg(
        "desolation_aloha", "Desolation Wilderness: Lake Aloha Backcountry", "Desolation Wilderness", "Sierra Wilderness Areas", "US Forest Service (Eldorado NF)",
        38.8685, -120.1342, "Paid Wilderness Permit", "Wilderness backpacking quota permits open 6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/permits/233261", "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78424",
        40, "Glaciated granite wilderness campsites on islands & peninsulas across 63,960 acres", "$10/person/night + permit",
        10.0, 10.0, 1.5, 9, "Jul – Sep (Lakes thawed & warm)", "Jun & Oct",
        "Frozen under thick ice and heavy alpine snowpack Nov–May. Serious mountaineering terrain.",
        "California's most famous glaciated alpine lake: a shallow reservoir dotted with hundreds of white granite islands beneath Pyramid Peak.",
        "Pyramid Peak (9,983 ft), Pacific Crest Trail (PCT), Susie Lake, Heather Lake, Mosquito Pass"
    ),
    make_cg(
        "mokelumne_woods_lake", "Mokelumne Wilderness: Woods Lake Camp", "Mokelumne Wilderness", "Sierra Wilderness Areas", "US Forest Service (Eldorado NF)",
        38.6942, -119.9881, "Paid Reservation + FCFS", "Woods Lake on Recreation.gov (6 months rolling); Wilderness backpacking self-issued at Carson Pass",
        "https://www.recreation.gov/camping/campgrounds/232049", "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78426",
        25, "Drive-in tent sites at Woods Lake (8,200 ft elevation)", "$28",
        10.0, 10.0, 5.0, 7, "Jul – Aug (Wildflower superbloom)", "Sep – Oct",
        "HOME OF CARSON PASS SNO-PARK: Carson Pass (8,574 ft) is one of the highest maintained winter passes in California (Hwy 88). Heavy snowfall makes it a premier haven for snowshoers and XC skiers trekking to frozen Frog Lake.",
        "Famous for California's most spectacular alpine wildflower displays in July along the trail to Winnemucca Lake and Round Top (10,381 ft).",
        "Round Top peak (10,381 ft), Winnemucca Lake wildflower meadows, Frog Lake, Fourth of July Lake, Pacific Crest Trail"
    ),
    make_cg(
        "mokelumne_caples_lake", "Mokelumne Wilderness: Caples Lake Camp", "Mokelumne Wilderness", "Sierra Wilderness Areas", "US Forest Service (Eldorado NF)",
        38.7052, -120.0412, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232050", "https://www.fs.usda.gov/recarea/eldorado/recarea/?recid=78426",
        35, "Tent and RV campsites along Caples Lake shoreline under lodgepole pine", "$30",
        9.0, 9.5, 6.5, 7, "Jun – Sep", "Oct & May",
        "Heavy winter snow; Kirkwood Mountain Resort is just 5 miles away on Hwy 88.",
        "Situated on the forested northern shore of Caples Lake with trout fishing, kayak launching, and views of Round Top.",
        "Caples Lake trail, Emigrant Lake, Kirkwood Mountain Resort, Carson Pass"
    ),
    make_cg(
        "emigrant_kennedy_meadows", "Emigrant Wilderness: Kennedy Meadows", "Emigrant Wilderness", "Sierra Wilderness Areas", "US Forest Service (Stanislaus NF)",
        38.3006, -119.7428, "First-Come, First-Served / Free Wilderness Permit", "Campground is 100% FCFS ($20); Wilderness permits are FREE and self-issued at Summit Ranger Station",
        "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981", "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981",
        45, "Drive-in riverside campsites at pack station + 113,000 acres of wilderness backpacking", "$20 (trailhead) / $0 (wilderness)",
        10.0, 10.0, 4.0, 5, "Jul – Sep (Passes snow-free)", "Jun & Oct",
        "Sonora Pass (Hwy 108) closes completely with the first major winter storm (Nov to May). Inaccessible by car in deep winter.",
        "The uncrowded sister to Yosemite. Smooth glaciated granite bowls, clear trout streams (Middle Fork Stanislaus River), and sprawling trails.",
        "Relief Reservoir, Kennedy Lake, Sonora Pass (9,624 ft) PCT crossing, Leavitt Falls, Columns of the Giants"
    ),
    make_cg(
        "emigrant_baker_deadman", "Sonora Pass: Baker & Deadman Camps", "Emigrant Wilderness", "Sierra Wilderness Areas", "US Forest Service (Stanislaus NF)",
        38.3185, -119.6842, "First-Come, First-Served", "100% First-Come, First-Served along Highway 108 corridor",
        "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981", "https://www.fs.usda.gov/recarea/stanislaus/recarea/?recid=14981",
        60, "Riverside campsites shaded by Jeffrey pine along Middle Fork Stanislaus River", "$20 - $22",
        9.5, 9.5, 4.5, 5, "Jul – Sep", "Closed in winter",
        "Closed Nov–May due to seasonal closure of Sonora Pass (Hwy 108).",
        "Beautiful high-altitude forested campsites along rushing mountain rivers directly on the Sonora Pass scenic highway route.",
        "Sonora Pass granite peaks, Saint Mary's Pass trail, Pacific Crest Trail"
    ),

    # -------------------------------------------------------------
    # 12. EASTERN SIERRA & MONO COUNTY
    # -------------------------------------------------------------
    make_cg(
        "june_lake_oh_ridge", "June Lake Loop: Oh! Ridge Campground", "June Lake Loop", "Eastern Sierra & Mono County", "US Forest Service (Inyo NF)",
        37.7858, -119.0683, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232014", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20562",
        144, "Drive-in tent and RV sites perched above sandy lake beach", "$34",
        9.5, 10.0, 7.5, 8, "Jul – Aug (Beach) & late Sep – Oct (Golden fall foliage)", "May & Nov",
        "Campground closes mid-October due to freezing temperatures. However, June Mountain ski resort opens Dec–April with steep powder bowls.",
        "Known as the 'Switzerland of California.' Perched on a sandy bluff above June Lake with swimming beach, trout fishing, and views of Carson Peak.",
        "Parker Lake trail, Fern Lake, Rush Creek Trail into Ansel Adams Wilderness & Thousand Island Lake, Gull Lake"
    ),
    make_cg(
        "june_lake_silver", "June Lake Loop: Silver Lake Campground", "June Lake Loop", "Eastern Sierra & Mono County", "US Forest Service (Inyo NF)",
        37.7692, -119.1245, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232015", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20562",
        63, "Campsites nestled under Carson Peak along Silver Lake & Rush Creek", "$32",
        10.0, 10.0, 7.0, 8, "Jun – Oct (Spectacular autumn foliage)", "Closed in winter",
        "Closed in winter. Prime autumn leaf-peeping location in late September and October.",
        "Situated at the base of the sheer 10,909-foot Carson Peak along Rush Creek and Silver Lake. Starting point for the Rush Creek Trail into Ansel Adams Wilderness.",
        "Rush Creek Trail to Agnew Lake & Gem Lake, Ansel Adams Wilderness, Silver Lake marina"
    ),
    make_cg(
        "mammoth_coldwater", "Mammoth Lakes: Coldwater Campground", "Mammoth Lakes Basin", "Eastern Sierra & Mono County", "US Forest Service (Inyo NF)",
        37.5956, -118.9958, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232009", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20572",
        74, "Drive-in tent and RV sites at 9,000 ft elevation along Coldwater Creek", "$32",
        10.0, 10.0, 7.0, 8, "Jul – Aug (Alpine summer) & Nov – Apr (Mammoth ski season)", "Jun & Sep – Oct",
        "WORLD-CLASS WINTER SPORTS CAPITAL: Campground closed Oct–May under feet of snow. Mammoth Mountain (11,053 ft) offers 3,500 acres of ski terrain. Winter snowshoeing and XC skiing at Tamarack Lodge.",
        "High alpine wonderland at 9,000 feet in the Mammoth Lakes Basin. Direct trailhead access to Duck Pass, Emerald Lake, and Barney Lake.",
        "Duck Pass Trail, Devils Postpile geometric basalt columns, Rainbow Falls (101-ft cascade), Crystal Lake, Mammoth Crest"
    ),
    make_cg(
        "mammoth_lake_mary", "Mammoth Lakes: Lake Mary Campground", "Mammoth Lakes Basin", "Eastern Sierra & Mono County", "US Forest Service (Inyo NF)",
        37.6012, -118.9985, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232010", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20572",
        48, "Campsites on crystal Lake Mary with marina & paddleboard rentals", "$32",
        9.5, 10.0, 7.5, 8, "Jul – Aug", "Closed in winter",
        "Buried in snow in winter; winter cross-country ski trails groomed right across frozen Lake Mary by Tamarack Lodge.",
        "Camp right on the shores of Lake Mary, the largest lake in the Mammoth Lakes Basin. Crystal clear waters and alpine peaks.",
        "Lake Mary loop, Crystal Crag, Lake George, Panorama Dome"
    ),
    make_cg(
        "convict_lake", "Convict Lake Campground", "Convict Lake Basin", "Eastern Sierra & Mono County", "US Forest Service (Inyo NF)",
        37.5978, -118.8522, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232013", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20560",
        85, "Tent and RV sites along Convict Creek beneath towering cliffs", "$34",
        9.0, 10.0, 7.5, 8, "Jun – Aug (Summer fishing) & Oct (Fall foliage reflection)", "May & Sep",
        "Campground closes in late October. However, the lake road is plowed year-round, allowing breathtaking winter day visits to photograph Mount Morrison's sheer snow-dusted rock face.",
        "One of the most photogenic alpine lakes in the world. Mount Morrison rises 4,000 vertical feet directly from the shoreline.",
        "Convict Lake Loop Trail, Convict Creek Canyon Trail to Lake Genevieve (John Muir Wilderness), Hot Creek Geologic Site, Whitmore Hot Springs"
    ),
    make_cg(
        "mono_lake_travertine", "Mono Lake & Travertine Hot Springs", "Mono Lake Tufa Reserve", "Eastern Sierra & Mono County", "California State Parks / BLM",
        38.0019, -119.1417, "Dispersed BLM / First-Come First-Served", "Free BLM dispersed camping nearby (Travertine Hot Springs / Bridgeport) & USFS campgrounds at Tioga Pass",
        "https://www.monolake.org/", "https://www.parks.ca.gov/?page_id=514",
        40, "BLM dispersed sites and USFS creek-side campgrounds (Lundy Canyon / Moraine)", "$0 - $22",
        8.5, 10.0, 4.0, 4, "May – Oct", "Nov – Apr",
        "Travertine Hot Springs remains accessible in winter. Soaking in natural 103°F mineral pools while surrounded by winter snowdrifts overlooking the Sawtooth Ridge is an iconic Eastern Sierra winter ritual.",
        "Surreal desert-meets-mountain crossroads. Natural hot mineral springs with mountain vistas, eerie tufa towers at Mono Lake, and the remarkably preserved historic ghost town of Bodie.",
        "South Tufa Reserve boardwalk, Travertine Hot Springs, Buckeye Hot Springs, Bodie State Historic Park, Lundy Canyon waterfalls"
    ),

    # -------------------------------------------------------------
    # 13. EASTERN SIERRA & INYO COUNTY (PALISADES & MT WHITNEY)
    # -------------------------------------------------------------
    make_cg(
        "big_pine_creek", "Big Pine Creek Campground (Palisade Glacier)", "Big Pine Canyon", "Eastern Sierra & Inyo County", "US Forest Service (Inyo NF)",
        37.1264, -118.4383, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232016", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20268",
        30, "Drive-in tent and RV sites along roaring glacier-fed Big Pine Creek (7,700 ft)", "$28",
        10.0, 10.0, 5.0, 8, "Jul – Sep (Glacial lakes thawed into vibrant turquoise)", "Jun & Oct",
        "Campground closed in winter (Nov–Apr); road closed at lower glacier gate due to snow. Extreme mountaineers use it for winter ascents of the Palisade Glacier.",
        "Trailhead for the famed North Fork Big Pine Creek trail to Seven Lakes—fed by Palisade Glacier (the southernmost glacier in North America) giving turquoise-milky waters beneath Temple Crag (12,999 ft).",
        "Temple Crag, Big Pine Lakes 1-7, Palisade Glacier, South Fork Big Pine Creek to Brainerd Lake, Ancient Bristlecone Pine Forest"
    ),
    make_cg(
        "whitney_portal", "Whitney Portal Campground (Mount Whitney Base)", "Whitney Portal", "Eastern Sierra & Inyo County", "US Forest Service (Inyo NF)",
        36.5869, -118.2397, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov (Summit permits via annual lottery in February)",
        "https://www.recreation.gov/camping/campgrounds/232017", "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20696",
        43, "Drive-in tent sites nestled in thick pine forest at 8,360 ft", "$30",
        10.0, 10.0, 6.0, 9, "Jul – Sep (Mount Whitney summit snow-free window)", "May – Jun & Oct",
        "Whitney Portal Road closes in winter near the base. Heavy snow blankets the canyon; only accessible on foot/skis by experienced technical mountaineers tackling the Mountaineer's Route.",
        "The official starting point for hiking Mount Whitney (14,505 ft, highest peak in the contiguous US). Shaded by giant ponderosa and Jeffrey pines alongside roaring waterfalls.",
        "Mount Whitney Trail (22 miles round trip, 6,100 ft elevation gain), Lone Pine Lake (no permit required day-hike), Meysan Lake, Alabama Hills"
    ),
    make_cg(
        "alabama_hills_movie", "Alabama Hills: Movie Flat Dispersed", "Alabama Hills National Scenic Area", "Eastern Sierra & Inyo County", "Bureau of Land Management (BLM)",
        36.6083, -118.1153, "Dispersed / Designated Semi-Primitive (Free)", "No reservations - Designated dispersed sites (Free $0). Follow BLM designated camping posts.",
        "https://www.blm.gov/programs/national-conservation-lands/california/alabama-hills-national-scenic-area", "https://www.blm.gov/programs/national-conservation-lands/california/alabama-hills-national-scenic-area",
        50, "Primitive vehicle dispersed campsites nestled in golden granite boulder mazes", "Free ($0)",
        8.5, 10.0, 1.5, 5, "Oct – Apr (Pleasant winter/spring desert temperatures)", "Jun – Aug (Blistering 105°F heat)",
        "PRIME WINTER CAMPING DESTINATION! While the high Sierra peaks above are frozen under 15 feet of snow, the Alabama Hills enjoy crisp, sunny winter days (55–65°F) and cool nights. Unmatched winter photography with rounded warm rocks framing snow-capped Mount Whitney.",
        "World-famous golden granite rock arches and rounded labyrinth boulders sitting directly beneath the towering 14,000-foot snow-capped eastern face of the Sierra Nevada.",
        "Mobius Arch Loop Trail, Movie Road, Shark's Tooth, Mount Whitney Fish Hatchery, Museum of Western Film History in Lone Pine"
    ),

    # -------------------------------------------------------------
    # 14. HIGH SIERRA & YOSEMITE NATIONAL PARK
    # -------------------------------------------------------------
    make_cg(
        "yosemite_upper_pines", "Yosemite: Upper Pines Campground", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.7425, -119.5719, "Paid Reservation", "Released on 15th of each month at 7:00 AM PT for 5 months ahead on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232447", "https://www.nps.gov/yose/planyourvisit/campgrounds.htm",
        238, "Drive-in tent and RV sites in Yosemite Valley along Merced River", "$36",
        10.0, 10.0, 8.0, 10, "May – Oct (Sold out in seconds)", "Nov – Mar (Winter wonderland)",
        "Open year-round! Winter in Yosemite Valley brings snow-dusted granite walls, ice skating in Half Dome village, and frozen waterfalls. Tire chains often required on Valley roads.",
        "The flagship campground in Yosemite Valley. Located at the foot of Half Dome and Glacier Point, steps from the Mist Trail and Happy Isles.",
        "Mist Trail (Vernal & Nevada Falls), Half Dome cables, Mirror Lake, John Muir Trail, Glacier Point"
    ),
    make_cg(
        "yosemite_lower_pines", "Yosemite: Lower Pines Campground", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.7405, -119.5742, "Paid Reservation", "Released on 15th of each month at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232446", "https://www.nps.gov/yose/planyourvisit/campgrounds.htm",
        60, "Drive-in tent and RV sites along the tranquil Merced River", "$36",
        10.0, 10.0, 8.0, 10, "Apr – Oct", "Closed in winter",
        "Closed Nov–Mar. Opens in spring as snowmelt fills the Merced River.",
        "Intimate campground in Yosemite Valley with beautiful river-facing campsites directly beneath Half Dome.",
        "Merced River beaches, Curry Village, Mist Trail, Yosemite Valley Shuttle"
    ),
    make_cg(
        "yosemite_north_pines", "Yosemite: North Pines Campground", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.7445, -119.5695, "Paid Reservation", "Released on 15th of each month at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232449", "https://www.nps.gov/yose/planyourvisit/campgrounds.htm",
        81, "Drive-in sites at confluence of Merced River and Tenaya Creek", "$36",
        10.0, 10.0, 8.0, 10, "Apr – Oct", "Closed in winter",
        "Closed Nov–Mar due to winter river flooding and snow.",
        "Nestled beneath the sheer rock wall of Washington Column and Royal Arches where Tenaya Creek flows into the Merced River.",
        "Tenaya Creek, Mirror Lake trail, Washington Column, Half Dome views"
    ),
    make_cg(
        "yosemite_camp_4", "Yosemite: Camp 4 (Climbers Camp)", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.7412, -119.6012, "Daily Lottery (Rec.gov)", "1-day advance daily lottery on Recreation.gov ($10/person/night)",
        "https://www.recreation.gov/camping/campgrounds/10004144", "https://www.nps.gov/yose/planyourvisit/camp4.htm",
        35, "Shared walk-in tent campsites beneath granite boulders", "$10 / person / night",
        10.0, 9.5, 4.0, 10, "May – Oct (Peak climbing season)", "Nov – Mar (Winter walk-up)",
        "Open year-round; winter walk-up registration at kiosk; quiet and peaceful under snow.",
        "National Register of Historic Places site. The spiritual home of world rock climbing beneath El Capitan and Yosemite Falls.",
        "Columbia Rock, Upper Yosemite Falls trail, El Capitan Meadow, Midnight Lightning boulder"
    ),
    make_cg(
        "yosemite_tuolumne", "Yosemite: Tuolumne Meadows Campground", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.8735, -119.3562, "Paid Reservation", "Released on 15th of each month on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232448", "https://www.nps.gov/yose/planyourvisit/campgrounds.htm",
        304, "Campsites at 8,600 ft along Tuolumne River in High Sierra", "$36",
        10.0, 10.0, 7.5, 10, "Jul – Sep (Only open ~10-12 weeks per year)", "Closed Nov – Jun (Buried in snow)",
        "Tioga Road (Hwy 120) closes completely Nov–May under 15–20 feet of snow.",
        "The crown jewel of Yosemite's high country at 8,600 feet. Subalpine meadows, glaciated granite domes, and crystalline alpine rivers.",
        "Lembert Dome, Cathedral Lakes, Lyell Canyon (PCT/JMT), Elizabeth Lake, Tuolumne River"
    ),
    make_cg(
        "yosemite_wawona", "Yosemite: Wawona Campground", "Yosemite National Park", "Sierra Nevada", "National Park Service",
        37.5372, -119.6585, "Paid Reservation", "Released on 15th of each month on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232451", "https://www.nps.gov/yose/planyourvisit/campgrounds.htm",
        93, "Campsites along South Fork Merced River near Mariposa Grove", "$36",
        9.0, 9.0, 8.0, 8, "May – Oct", "Nov – Mar (Loop A open year-round)",
        "Loop A stays open year-round in winter; snowshoeing among the Giant Sequoias in Mariposa Grove is extraordinary.",
        "Located along the South Fork of the Merced River near the historic Wawona Hotel and the Mariposa Grove of Giant Sequoias.",
        "Mariposa Grove of Giant Sequoias (Grizzly Giant, California Tunnel Tree), Chilnualna Falls, swinging bridge"
    ),
    make_cg(
        "calaveras_big_trees", "Calaveras Big Trees State Park", "Calaveras Big Trees State Park", "Sierra Nevada", "California State Parks",
        38.2778, -120.3117, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/703", "https://www.parks.ca.gov/?page_id=551",
        129, "Drive-in tent & RV sites, cabins", "$35",
        9.0, 9.0, 8.5, 8, "May – Sep", "Nov – Mar (Winter snowshoeing)",
        "Open year-round; winter brings magical snowshoeing through the North Grove among massive snow-covered Giant Sequoias.",
        "Home to ancient Giant Sequoias (Sequoiadendron giganteum) up to 3,000 years old along the crystal Stanislaus River.",
        "North Grove Giant Sequoias, South Grove Trail, Stanislaus River swimming at Beaver Creek"
    ),

    # -------------------------------------------------------------
    # 15. SHASTA-CASCADE & TRINITY ALPS
    # -------------------------------------------------------------
    make_cg(
        "castle_crags", "Castle Crags State Park", "Castle Crags State Park", "Shasta / Trinity / Cascade", "California State Parks",
        41.1578, -122.3236, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia (some FCFS sites off-season)",
        "https://www.reservecalifornia.com/Web/#!park/728", "https://www.parks.ca.gov/?page_id=454",
        76, "Drive-in tent & RV sites (no hookups)", "$35",
        10.0, 9.5, 7.5, 7, "May – Oct", "Nov – Mar",
        "Open year-round; snow dusts the towering granite crags in winter; lower riverside loop accessible.",
        "Dramatic 6,000-foot granite spires looming above pine forests with jaw-dropping views of snow-capped Mt. Shasta.",
        "Crags Trail to Castle Dome (6,000-ft granite spires), Pacific Crest Trail (PCT), Upper Sacramento River trout fishing"
    ),
    make_cg(
        "lake_shasta_antlers", "Lake Shasta: Antlers Campground", "Lake Shasta Recreation Area", "Shasta / Trinity / Cascade", "US Forest Service (Shasta-Trinity NF)",
        40.9022, -122.4219, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232860", "https://www.fs.usda.gov/recarea/stnf/recarea/?recid=6486",
        59, "Drive-in tent & RV sites in oak & pine forest on Sacramento Arm", "$28 - $36",
        7.5, 8.5, 7.5, 6, "May – Sep", "Nov – Mar",
        "Open year-round; mild winter boating and fishing.",
        "Warm water reservoir recreation surrounded by forested mountain inlets with great swimming and boat access.",
        "Lake Shasta Caverns, Bailey Cove Trail, Shasta Dam, water skiing and houseboating"
    ),
    make_cg(
        "whiskeytown_oak_bottom", "Whiskeytown: Oak Bottom Tent Camp", "Whiskeytown National Rec Area", "Shasta / Trinity / Cascade", "National Park Service",
        40.6128, -122.5694, "Paid Reservation", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/233267", "https://www.nps.gov/whis/planyourvisit/camping.htm",
        92, "Walk-in tent sites right on the sandy mountain lakeshore", "$25",
        9.0, 9.0, 7.5, 7, "May – Sep", "Nov – Mar",
        "Open year-round; winter waterfalls flow strongly; crisp lakefront solitude.",
        "Crystal-clear mountain lake ringed by pine forests and multi-tier waterfalls; walk-in tent sites right on the sandy shore.",
        "Whiskeytown Falls (220-ft cascade), Crystal Creek Falls, kayak tours, Mt. Shasta vistas"
    ),
    make_cg(
        "trinity_lake_hayward", "Trinity Lake: Hayward Flat Camp", "Trinity Lake Recreation Area", "Shasta / Trinity / Cascade", "US Forest Service (Shasta-Trinity NF)",
        40.8931, -122.7842, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov",
        "https://www.recreation.gov/camping/campgrounds/232862", "https://www.fs.usda.gov/recarea/stnf/recarea/?recid=6492",
        98, "Tent and RV campsites in pine forest along Stuart Fork Arm", "$25 - $32",
        8.5, 8.5, 7.5, 5, "May – Sep", "Nov – Mar",
        "Open seasonally May–Oct; serene mountain setting under the Trinity Alps.",
        "Peaceful, uncrowded alternative to Shasta tucked into deep conifer forest under the rugged Trinity Alps.",
        "Trinity Alps Wilderness trailheads, Trinity River fly fishing, Bowerman Ridge, lake boating"
    ),
    make_cg(
        "trinity_alps_bridge_camp", "Trinity Alps: Bridge Camp Trailhead", "Trinity Alps Wilderness", "Shasta / Trinity / Cascade", "US Forest Service / BLM",
        40.9167, -122.9583, "First-Come, First-Served / Free Wilderness Permit", "FCFS trailhead camping ($10-$15) + Free Wilderness Backpacking Permit",
        "https://www.fs.usda.gov/recarea/stnf/recarea/?recid=6521", "https://www.fs.usda.gov/recarea/stnf/recarea/?recid=6521",
        35, "Primitive trailhead campsites & infinite backcountry wilderness camping", "$0 - $15",
        10.0, 10.0, 3.5, 4, "Jul – Sep (High passes snow-free)", "Nov – Apr (Heavy snow)",
        "High alpine wilderness frozen under heavy snow in winter; mountaineering only.",
        "The Switzerland of California. Glacial cirques, jagged granite ridges, and azure alpine tarns with uncrowded solitude.",
        "Canyon Creek Lakes, Caribou Basin, Stuart Fork Trail to Emerald & Sapphire Lakes"
    ),
    make_cg(
        "burney_falls", "McArthur-Burney Falls State Park", "McArthur-Burney Falls Memorial State Park", "Shasta / Trinity / Cascade", "California State Parks",
        41.0117, -121.6514, "Paid Reservation", "6 months rolling at 8:00 AM PT on ReserveCalifornia",
        "https://www.reservecalifornia.com/Web/#!park/724", "https://www.parks.ca.gov/?page_id=455",
        121, "Drive-in tent & RV sites, 24 rustic cabins", "$35 ($105 cabins)",
        8.5, 9.5, 8.5, 8, "May – Sep", "Nov – Mar",
        "Open year-round; winter snow transforms Burney Falls into an icy fairy tale; heated cabins available.",
        "Roaring 129-foot spring-fed waterfall gushing 100 million gallons of cold water daily from volcanic basalt underground springs.",
        "129-foot Burney Falls ('Eighth Wonder of the World'), Lake Britton swim beach, Pacific Crest Trail"
    ),
    make_cg(
        "lassen_manzanita", "Lassen Volcanic: Manzanita Lake Camp", "Lassen Volcanic National Park", "Shasta / Trinity / Cascade", "National Park Service",
        40.5342, -121.5647, "Paid Reservation + FCFS", "6 months rolling at 7:00 AM PT on Recreation.gov + Loop C/D walk-ins",
        "https://www.recreation.gov/camping/campgrounds/232450", "https://www.nps.gov/lavo/planyourvisit/manzanita-lake-campground.htm",
        179, "Tent, RV (no hookups), 20 rustic camping cabins", "$26 ($75 cabins)",
        10.0, 10.0, 7.5, 8, "Jul – Sep (Pass snow-free)", "Closed Nov – May (Buried in snow)",
        "Lassen Park Highway buried under 20+ feet of snow in winter. Snowshoeing and cross-country ski touring from Kohm Yah-mah-nee Visitor Center.",
        "All four volcano types represented! Reflective alpine lake with kayak rentals looking directly at Lassen Peak.",
        "Lassen Peak summit (10,457 ft), Bumpass Hell hydrothermal boardwalk, Manzanita Lake loop, Cinder Cone"
    )
]

# Sort by driving distance from Home
all_cgs.sort(key=lambda x: x["distance_road_miles"])

payload = {
    "home_point": HOME,
    "total_campgrounds": len(all_cgs),
    "campgrounds": all_cgs
}

with open("campgrounds_data.json", "w") as f:
    json.dump(payload, f, indent=2)

print(f"Successfully generated campgrounds_data.json with {len(all_cgs)} individually listed campgrounds!")
