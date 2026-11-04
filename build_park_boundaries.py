# build_park_boundaries.py
import json

# Comprehensive GeoJSON boundary polygons for California Parks & Wilderness Areas
# Coordinates are [longitude, latitude] in GeoJSON format

features = []

def make_poly(name, category, agency, acres, color, fill_color, fill_opacity, dash_array, coords, desc=""):
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "category": category,
            "agency": agency,
            "acres": acres,
            "color": color,
            "fillColor": fill_color,
            "fillOpacity": fill_opacity,
            "dashArray": dash_array,
            "description": desc
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords]
        }
    }

# -------------------------------------------------------------
# 1. NATIONAL PARKS & SEASHORES (Sky Blue / Deep Navy)
# -------------------------------------------------------------
# Yosemite National Park (~750,000 acres)
yosemite_coords = [
    [-119.88, 38.18], [-119.65, 38.19], [-119.50, 38.12], [-119.28, 38.05],
    [-119.20, 37.92], [-119.22, 37.75], [-119.30, 37.60], [-119.45, 37.50],
    [-119.65, 37.48], [-119.82, 37.55], [-119.92, 37.72], [-119.98, 37.88],
    [-119.90, 38.05], [-119.88, 38.18]
]
features.append(make_poly(
    "Yosemite National Park", "National Park", "National Park Service", 750000,
    "#0284c7", "#38bdf8", 0.15, None, yosemite_coords,
    "World-renowned glaciated granite valley, giant sequoias, Half Dome, El Capitan, and high alpine meadows."
))

# Point Reyes National Seashore (~71,000 acres)
pt_reyes_coords = [
    [-122.98, 38.23], [-122.91, 38.18], [-122.84, 38.10], [-122.78, 38.02],
    [-122.74, 37.93], [-122.78, 37.92], [-122.84, 37.98], [-122.92, 38.02],
    [-123.02, 38.00], [-123.00, 38.07], [-122.95, 38.12], [-123.04, 38.20],
    [-122.98, 38.23]
]
features.append(make_poly(
    "Point Reyes National Seashore", "National Park / Seashore", "National Park Service", 71000,
    "#0284c7", "#38bdf8", 0.18, None, pt_reyes_coords,
    "Wild Pacific coastal wilderness, tidefall waterfall Alamere Falls, tule elk reserve, and coastal backcountry trail camps."
))

# Lassen Volcanic National Park (~106,000 acres)
lassen_coords = [
    [-121.60, 40.56], [-121.40, 40.57], [-121.35, 40.48], [-121.36, 40.40],
    [-121.48, 40.39], [-121.60, 40.45], [-121.62, 40.52], [-121.60, 40.56]
]
features.append(make_poly(
    "Lassen Volcanic National Park", "National Park", "National Park Service", 106000,
    "#0284c7", "#38bdf8", 0.15, None, lassen_coords,
    "All four volcano types represented: Lassen Peak, Bumpass Hell hydrothermal boardwalk, Manzanita Lake, and Cinder Cone."
))

# Pinnacles National Park (~26,000 acres)
pinnacles_coords = [
    [-121.22, 36.54], [-121.14, 36.53], [-121.12, 36.46], [-121.18, 36.44],
    [-121.24, 36.47], [-121.25, 36.52], [-121.22, 36.54]
]
features.append(make_poly(
    "Pinnacles National Park", "National Park", "National Park Service", 26000,
    "#0284c7", "#38bdf8", 0.16, None, pinnacles_coords,
    "Volcanic spires, talus caves, soaring California Condors, and High Peaks climbing trails."
))

# Marin Headlands (GGNRA) (~15,000 acres)
marin_headlands_coords = [
    [-122.56, 37.86], [-122.49, 37.84], [-122.47, 37.82], [-122.52, 37.81],
    [-122.55, 37.83], [-122.56, 37.86]
]
features.append(make_poly(
    "Marin Headlands (GGNRA)", "National Recreation Area", "National Park Service", 15000,
    "#0284c7", "#38bdf8", 0.18, None, marin_headlands_coords,
    "Golden Gate coastal bluffs, Kirby Cove, Hawk Hill raptor migration, and historic military batteries."
))

# Whiskeytown National Recreation Area (~42,000 acres)
whiskeytown_coords = [
    [-122.62, 40.66], [-122.50, 40.67], [-122.48, 40.58], [-122.60, 40.57],
    [-122.65, 40.61], [-122.62, 40.66]
]
features.append(make_poly(
    "Whiskeytown National Recreation Area", "National Recreation Area", "National Park Service", 42000,
    "#0284c7", "#38bdf8", 0.15, None, whiskeytown_coords,
    "Crystal-clear mountain lake ringed by pine forests and multi-tier waterfalls like Whiskeytown Falls."
))

# -------------------------------------------------------------
# 2. NATIONAL WILDERNESS AREAS (Purple / Violet with Dashed Outline)
# -------------------------------------------------------------
# Desolation Wilderness (~63,960 acres)
desolation_coords = [
    [-120.22, 39.02], [-120.08, 39.00], [-120.05, 38.93], [-120.06, 38.86],
    [-120.14, 38.83], [-120.22, 38.88], [-120.25, 38.96], [-120.22, 39.02]
]
features.append(make_poly(
    "Desolation Wilderness", "National Wilderness Area", "US Forest Service (Eldorado NF)", 63960,
    "#a855f7", "#c084fc", 0.20, "6, 6", desolation_coords,
    "Glaciated alpine granite wonderland: Lake Aloha, Mount Tallac (9,735 ft), Velma Lakes, and the Pacific Crest Trail."
))

# Mokelumne Wilderness (~105,165 acres)
mokelumne_coords = [
    [-120.15, 38.72], [-119.92, 38.71], [-119.86, 38.62], [-119.92, 38.52],
    [-120.10, 38.53], [-120.18, 38.62], [-120.15, 38.72]
]
features.append(make_poly(
    "Mokelumne Wilderness", "National Wilderness Area", "US Forest Service (Eldorado/Stanislaus)", 105165,
    "#a855f7", "#c084fc", 0.20, "6, 6", mokelumne_coords,
    "High alpine volcanic spires, July wildflower superblooms at Winnemucca Lake, Round Top (10,381 ft), and Carson Pass."
))

# Emigrant Wilderness (~113,000 acres)
emigrant_coords = [
    [-119.85, 38.35], [-119.60, 38.34], [-119.52, 38.22], [-119.65, 38.12],
    [-119.85, 38.15], [-119.90, 38.25], [-119.85, 38.35]
]
features.append(make_poly(
    "Emigrant Wilderness", "National Wilderness Area", "US Forest Service (Stanislaus NF)", 113000,
    "#a855f7", "#c084fc", 0.20, "6, 6", emigrant_coords,
    "Smooth glaciated granite bowls, uncrowded alpine lakes, Relief Reservoir, and Middle Fork Stanislaus River."
))

# Ansel Adams Wilderness (~231,533 acres)
ansel_adams_coords = [
    [-119.35, 37.82], [-119.12, 37.80], [-119.05, 37.68], [-119.15, 37.58],
    [-119.32, 37.62], [-119.38, 37.74], [-119.35, 37.82]
]
features.append(make_poly(
    "Ansel Adams Wilderness", "National Wilderness Area", "US Forest Service (Inyo/Sierra NF)", 231533,
    "#a855f7", "#c084fc", 0.20, "6, 6", ansel_adams_coords,
    "Jagged peaks of the Minarets, Mount Ritter, Banner Peak, Thousand Island Lake, and the John Muir Trail."
))

# John Muir Wilderness (~580,000 acres)
john_muir_coords = [
    [-119.15, 37.58], [-118.65, 37.40], [-118.25, 36.65], [-118.35, 36.55],
    [-118.55, 36.85], [-118.85, 37.15], [-119.15, 37.58]
]
features.append(make_poly(
    "John Muir Wilderness", "National Wilderness Area", "US Forest Service (Inyo/Sierra NF)", 580000,
    "#a855f7", "#c084fc", 0.18, "6, 6", john_muir_coords,
    "The spine of the High Sierra: Mount Whitney (14,505 ft), Palisade Glacier, Evolution Valley, and deep alpine canyons."
))

# Ventana Wilderness (~240,026 acres)
ventana_coords = [
    [-121.75, 36.38], [-121.52, 36.36], [-121.42, 36.20], [-121.40, 36.05],
    [-121.55, 36.02], [-121.68, 36.18], [-121.75, 36.38]
]
features.append(make_poly(
    "Ventana Wilderness", "National Wilderness Area", "US Forest Service (Los Padres NF)", 240026,
    "#a855f7", "#c084fc", 0.20, "6, 6", ventana_coords,
    "Steep coastal Big Sur wilderness, deep redwood canyons, Cone Peak (5,155 ft), and Big Sur River gorge."
))

# Trinity Alps Wilderness (~525,627 acres)
trinity_alps_coords = [
    [-123.18, 41.15], [-122.82, 41.16], [-122.75, 40.95], [-122.88, 40.85],
    [-123.15, 40.88], [-123.25, 41.02], [-123.18, 41.15]
]
features.append(make_poly(
    "Trinity Alps Wilderness", "National Wilderness Area", "US Forest Service (Shasta-Trinity/Klamath)", 525627,
    "#a855f7", "#c084fc", 0.18, "6, 6", trinity_alps_coords,
    "The Switzerland of California: glaciated granite cirques, Canyon Creek Lakes, Caribou Basin, and Thompson Peak."
))

# -------------------------------------------------------------
# 3. CALIFORNIA STATE PARKS (Emerald Green)
# -------------------------------------------------------------
# Mount Tamalpais State Park (~6,300 acres)
mt_tam_coords = [
    [-122.65, 37.93], [-122.58, 37.93], [-122.56, 37.91], [-122.59, 37.89],
    [-122.64, 37.89], [-122.66, 37.91], [-122.65, 37.93]
]
features.append(make_poly(
    "Mount Tamalpais State Park", "State Park", "California State Parks", 6300,
    "#059669", "#10b981", 0.20, None, mt_tam_coords,
    "Iconic Bay Area peak, Pantoll & Bootjack campgrounds, Steep Ravine cabins, Dipsea Trail, and old-growth redwoods."
))

# Samuel P. Taylor State Park (~2,882 acres)
sam_p_taylor_coords = [
    [-122.76, 38.04], [-122.70, 38.04], [-122.70, 38.00], [-122.75, 38.01],
    [-122.76, 38.04]
]
features.append(make_poly(
    "Samuel P. Taylor State Park", "State Park", "California State Parks", 2882,
    "#059669", "#10b981", 0.20, None, sam_p_taylor_coords,
    "Lush old-growth redwood grove along Lagunitas Creek with coho salmon runs and Cross Marin Bike Trail."
))

# China Camp State Park (~1,514 acres)
china_camp_coords = [
    [-122.51, 38.02], [-122.46, 38.01], [-122.47, 37.99], [-122.51, 38.00],
    [-122.51, 38.02]
]
features.append(make_poly(
    "China Camp State Park", "State Park", "California State Parks", 1514,
    "#059669", "#10b981", 0.20, None, china_camp_coords,
    "Oak and bay laurel woodlands along San Pablo Bay, 15 miles of mountain bike singletrack, and historic Chinese shrimp village."
))

# Angel Island State Park (~740 acres)
angel_island_coords = [
    [-122.44, 37.87], [-122.41, 37.87], [-122.41, 37.85], [-122.44, 37.85],
    [-122.44, 37.87]
]
features.append(make_poly(
    "Angel Island State Park", "State Park", "California State Parks", 740,
    "#059669", "#10b981", 0.25, None, angel_island_coords,
    "Island camping in SF Bay with 360-degree views of Golden Gate Bridge and San Francisco skyline."
))

# Big Basin Redwoods State Park (~18,000 acres)
big_basin_coords = [
    [-122.27, 37.20], [-122.18, 37.20], [-122.18, 37.13], [-122.25, 37.12],
    [-122.28, 37.16], [-122.27, 37.20]
]
features.append(make_poly(
    "Big Basin Redwoods State Park", "State Park", "California State Parks", 18000,
    "#059669", "#10b981", 0.20, None, big_basin_coords,
    "California's oldest state park (1902); resilient ancient redwoods, Berry Creek Falls, and Skyline-to-the-Sea trail."
))

# Henry Cowell Redwoods State Park (~4,650 acres)
henry_cowell_coords = [
    [-122.09, 37.07], [-122.04, 37.07], [-122.04, 37.02], [-122.09, 37.03],
    [-122.09, 37.07]
]
features.append(make_poly(
    "Henry Cowell Redwoods State Park", "State Park", "California State Parks", 4650,
    "#059669", "#10b981", 0.20, None, henry_cowell_coords,
    "Old Growth Redwood Grove with 275-foot trees, San Lorenzo River swimming, and Fall Creek unit."
))

# Portola Redwoods State Park (~2,800 acres)
portola_coords = [
    [-122.24, 37.27], [-122.19, 37.27], [-122.19, 37.24], [-122.24, 37.24],
    [-122.24, 37.27]
]
features.append(make_poly(
    "Portola Redwoods State Park", "State Park", "California State Parks", 2800,
    "#059669", "#10b981", 0.20, None, portola_coords,
    "Deep, quiet, rugged redwood canyon with Peters Creek Old Growth Grove and Tip Toe Falls."
))

# Butano State Park (~4,000 acres)
butano_coords = [
    [-122.36, 37.23], [-122.30, 37.23], [-122.30, 37.18], [-122.36, 37.19],
    [-122.36, 37.23]
]
features.append(make_poly(
    "Butano State Park", "State Park", "California State Parks", 4000,
    "#059669", "#10b981", 0.20, None, butano_coords,
    "Secluded redwood canyon cloaked in coastal fog and moss near Pescadero and Ano Nuevo elephant seals."
))

# Half Moon Bay State Beach (~181 acres)
half_moon_coords = [
    [-122.46, 37.49], [-122.43, 37.49], [-122.43, 37.44], [-122.46, 37.44],
    [-122.46, 37.49]
]
features.append(make_poly(
    "Half Moon Bay State Beach", "State Beach", "California State Parks", 181,
    "#059669", "#10b981", 0.25, None, half_moon_coords,
    "Coastal bluffs above Francis Beach with crashing waves, Coastside Trail, and Mavericks surf break nearby."
))

# Mount Diablo State Park (~20,000 acres)
mount_diablo_coords = [
    [-121.96, 37.91], [-121.88, 37.91], [-121.87, 37.84], [-121.96, 37.84],
    [-121.96, 37.91]
]
features.append(make_poly(
    "Mount Diablo State Park", "State Park", "California State Parks", 20000,
    "#059669", "#10b981", 0.20, None, mount_diablo_coords,
    "Panoramic 3,849-foot summit, Juniper and Live Oak campgrounds, Rock City sandstone mazes, and 40-county views."
))

# Henry W. Coe State Park (~87,000 acres)
henry_coe_coords = [
    [-121.60, 37.28], [-121.38, 37.26], [-121.37, 37.12], [-121.56, 37.12],
    [-121.62, 37.20], [-121.60, 37.28]
]
features.append(make_poly(
    "Henry W. Coe State Park", "State Park", "California State Parks", 87000,
    "#059669", "#10b981", 0.18, None, henry_coe_coords,
    "The largest state park in Northern California: rugged Diablo Range ridges, spring wildflower superblooms, and remote lakes."
))

# Sugarloaf Ridge State Park (~4,000 acres)
sugarloaf_coords = [
    [-122.54, 38.46], [-122.48, 38.46], [-122.48, 38.42], [-122.54, 38.42],
    [-122.54, 38.46]
]
features.append(make_poly(
    "Sugarloaf Ridge State Park", "State Park", "California State Parks", 4000,
    "#059669", "#10b981", 0.20, None, sugarloaf_coords,
    "Sonoma Valley dark skies, Robert Ferguson Observatory, Bald Mountain summit, and Sonoma Creek Falls."
))

# Bothe-Napa Valley State Park (~1,991 acres)
bothe_napa_coords = [
    [-122.55, 38.55], [-122.51, 38.55], [-122.51, 38.52], [-122.55, 38.52],
    [-122.55, 38.55]
]
features.append(make_poly(
    "Bothe-Napa Valley State Park", "State Park", "California State Parks", 1991,
    "#059669", "#10b981", 0.20, None, bothe_napa_coords,
    "Heart of Napa wine country; redwoods, Ritchey Creek, historic yurts and cabins, and spring-fed swimming pool."
))

# Sonoma Coast State Park (~5,000 acres)
sonoma_coast_coords = [
    [-123.10, 38.48], [-123.05, 38.48], [-123.00, 38.32], [-123.05, 38.30],
    [-123.10, 38.38], [-123.10, 38.48]
]
features.append(make_poly(
    "Sonoma Coast State Park", "State Park", "California State Parks", 5000,
    "#059669", "#10b981", 0.22, None, sonoma_coast_coords,
    "Dramatic Pacific bluffs from Bodega Head to Goat Rock seal colony, Wright's Beach beachfront camping, and Kortum Trail."
))

# Salt Point State Park (~6,000 acres)
salt_point_coords = [
    [-123.36, 38.60], [-123.30, 38.60], [-123.30, 38.54], [-123.36, 38.54],
    [-123.36, 38.60]
]
features.append(make_poly(
    "Salt Point State Park", "State Park", "California State Parks", 6000,
    "#059669", "#10b981", 0.20, None, salt_point_coords,
    "Tafoni sandstone rock pockets, Gerstle Cove Marine Reserve, Pygmy Forest, and bishop pine coastal woodlands."
))

# Russian Gulch & Van Damme State Parks (~3,000 acres)
mendocino_parks_coords = [
    [-123.82, 39.35], [-123.76, 39.35], [-123.76, 39.26], [-123.82, 39.26],
    [-123.82, 39.35]
]
features.append(make_poly(
    "Russian Gulch & Van Damme State Parks", "State Park", "California State Parks", 3000,
    "#059669", "#10b981", 0.20, None, mendocino_parks_coords,
    "Mendocino coast sea bridges, Devil's Punchbowl blowhole, Russian Gulch waterfall, and sea cave kayaking in Van Damme cove."
))

# Pfeiffer Big Sur State Park (~1,006 acres)
pfeiffer_big_sur_coords = [
    [-121.81, 36.27], [-121.75, 36.27], [-121.75, 36.23], [-121.81, 36.23],
    [-121.81, 36.27]
]
features.append(make_poly(
    "Pfeiffer Big Sur State Park", "State Park", "California State Parks", 1006,
    "#059669", "#10b981", 0.25, None, pfeiffer_big_sur_coords,
    "Quintessential Big Sur: towering redwoods along the Big Sur River, swimming gorge, and Buzzard's Roost Trail."
))

# Julia Pfeiffer Burns State Park (~3,762 acres)
julia_pfeiffer_coords = [
    [-121.69, 36.18], [-121.65, 36.18], [-121.65, 36.14], [-121.69, 36.14],
    [-121.69, 36.18]
]
features.append(make_poly(
    "Julia Pfeiffer Burns State Park", "State Park", "California State Parks", 3762,
    "#059669", "#10b981", 0.25, None, julia_pfeiffer_coords,
    "Legendary McWay Falls plunging 80 feet directly into a turquoise Pacific cove, Ewoldsen Trail, and cliffside walk-in camps."
))

# Fremont Peak State Park (~298 acres)
fremont_peak_coords = [
    [-121.52, 36.78], [-121.48, 36.78], [-121.48, 36.75], [-121.52, 36.75],
    [-121.52, 36.78]
]
features.append(make_poly(
    "Fremont Peak State Park", "State Park", "California State Parks", 298,
    "#059669", "#10b981", 0.25, None, fremont_peak_coords,
    "High ridge 3,169-ft peak above Salinas Valley with Fremont Peak Astronomical Observatory and Monterey Bay sunset vistas."
))

# Calaveras Big Trees State Park (~6,500 acres)
calaveras_coords = [
    [-120.35, 38.31], [-120.26, 38.31], [-120.26, 38.25], [-120.35, 38.25],
    [-120.35, 38.31]
]
features.append(make_poly(
    "Calaveras Big Trees State Park", "State Park", "California State Parks", 6500,
    "#059669", "#10b981", 0.20, None, calaveras_coords,
    "North and South Groves of ancient Giant Sequoias up to 3,000 years old along the crystal-clear Stanislaus River."
))

# Sugar Pine Point State Park (~2,500 acres)
sugar_pine_coords = [
    [-120.15, 39.07], [-120.10, 39.07], [-120.10, 39.04], [-120.15, 39.04],
    [-120.15, 39.07]
]
features.append(make_poly(
    "Sugar Pine Point State Park", "State Park", "California State Parks", 2500,
    "#059669", "#10b981", 0.22, None, sugar_pine_coords,
    "Lake Tahoe's premier winter snow-camping park with heated restrooms, 1960 Olympic Nordic trails, and pristine summer beaches."
))

# Emerald Bay & D.L. Bliss State Parks (~3,300 acres)
emerald_bliss_coords = [
    [-120.13, 39.01], [-120.07, 39.01], [-120.07, 38.93], [-120.13, 38.93],
    [-120.13, 39.01]
]
features.append(make_poly(
    "Emerald Bay & D.L. Bliss State Parks", "State Park", "California State Parks", 3300,
    "#059669", "#10b981", 0.22, None, emerald_bliss_coords,
    "Fannette Island, Vikingsholm castle, Eagle Falls, Calawee Cove boulder beaches, and the famed Rubicon Trail."
))

# Donner Memorial State Park (~3,293 acres)
donner_coords = [
    [-120.25, 39.33], [-120.21, 39.33], [-120.21, 39.31], [-120.25, 39.31],
    [-120.25, 39.33]
]
features.append(make_poly(
    "Donner Memorial State Park", "State Park", "California State Parks", 3293,
    "#059669", "#10b981", 0.22, None, donner_coords,
    "East shore of Donner Lake in Truckee; winter groomed Nordic ski & snowshoe trails, summer swimming beach, and pioneer history museum."
))

# Castle Crags State Park (~4,350 acres)
castle_crags_coords = [
    [-122.38, 41.19], [-122.28, 41.19], [-122.28, 41.13], [-122.38, 41.13],
    [-122.38, 41.19]
]
features.append(make_poly(
    "Castle Crags State Park", "State Park", "California State Parks", 4350,
    "#059669", "#10b981", 0.20, None, castle_crags_coords,
    "6,000-foot granite spires looming above pine forests with jaw-dropping views of snow-capped Mt. Shasta."
))

# McArthur-Burney Falls Memorial State Park (~910 acres)
burney_falls_coords = [
    [-121.67, 41.03], [-121.63, 41.03], [-121.63, 41.00], [-121.67, 41.00],
    [-121.67, 41.03]
]
features.append(make_poly(
    "McArthur-Burney Falls State Park", "State Park", "California State Parks", 910,
    "#059669", "#10b981", 0.25, None, burney_falls_coords,
    "129-foot spring-fed Burney Falls ('Eighth Wonder of the World') gushing 100 million gallons daily into an azure pool."
))

# -------------------------------------------------------------
# 4. REGIONAL, COUNTY & BLM SCENIC AREAS (Amber / Pink)
# -------------------------------------------------------------
# Alabama Hills National Scenic Area (~30,000 acres)
alabama_hills_coords = [
    [-118.15, 36.65], [-118.08, 36.65], [-118.08, 36.57], [-118.15, 36.57],
    [-118.15, 36.65]
]
features.append(make_poly(
    "Alabama Hills National Scenic Area", "National Scenic Area", "Bureau of Land Management (BLM)", 30000,
    "#f59e0b", "#fbbf24", 0.20, None, alabama_hills_coords,
    "World-famous golden granite rock arches and rounded labyrinth boulders directly beneath snow-capped Mount Whitney."
))

# Lake Tahoe-Nevada State Park (~14,300 acres)
lake_tahoe_nv_coords = [
    [-119.95, 39.22], [-119.88, 39.22], [-119.88, 39.08], [-119.95, 39.08],
    [-119.95, 39.22]
]
features.append(make_poly(
    "Lake Tahoe-Nevada State Park", "State Park (NV)", "Nevada State Parks", 14300,
    "#059669", "#10b981", 0.20, None, lake_tahoe_nv_coords,
    "Sand Harbor crystal-turquoise boulder coves, Spooner Lake cross-country ski trails, and the famed Marlette Flume Trail."
))

# Mount Madonna County Park (~4,605 acres)
mt_madonna_coords = [
    [-121.73, 37.03], [-121.68, 37.03], [-121.68, 36.99], [-121.73, 36.99],
    [-121.73, 37.03]
]
features.append(make_poly(
    "Mount Madonna County Park", "County Park", "Santa Clara County Parks", 4605,
    "#db2777", "#f472b6", 0.18, None, mt_madonna_coords,
    "Coast redwood forest on the mountain ridge between Gilroy and Watsonville; canvas yurts and white deer sanctuary."
))

# Sanborn County Park (~3,453 acres)
sanborn_coords = [
    [-122.08, 37.25], [-122.04, 37.25], [-122.04, 37.22], [-122.08, 37.22],
    [-122.08, 37.25]
]
features.append(make_poly(
    "Sanborn County Park", "County Park", "Santa Clara County Parks", 3453,
    "#db2777", "#f472b6", 0.18, None, sanborn_coords,
    "Lush redwood forest above Saratoga with direct trail connection to Castle Rock State Park sandstone spires."
))

# Uvas Canyon County Park (~1,133 acres)
uvas_canyon_coords = [
    [-121.81, 37.10], [-121.77, 37.10], [-121.77, 37.07], [-121.81, 37.07],
    [-121.81, 37.10]
]
features.append(make_poly(
    "Uvas Canyon County Park", "County Park", "Santa Clara County Parks", 1133,
    "#db2777", "#f472b6", 0.18, None, uvas_canyon_coords,
    "Lush waterfall canyon featuring six cascading multi-tier natural waterfalls along Swanson Creek."
))

# Memorial County Park (~673 acres)
memorial_coords = [
    [-122.31, 37.29], [-122.26, 37.29], [-122.26, 37.26], [-122.31, 37.26],
    [-122.31, 37.29]
]
features.append(make_poly(
    "Memorial County Park", "County Park", "San Mateo County Parks", 673,
    "#db2777", "#f472b6", 0.18, None, memorial_coords,
    "Historic coast redwood park along Pescadero Creek with natural swimming holes and Mt. Ellen trail."
))

# Anthony Chabot Regional Park (~5,067 acres)
chabot_coords = [
    [-122.13, 37.78], [-122.07, 37.78], [-122.07, 37.73], [-122.13, 37.73],
    [-122.13, 37.78]
]
features.append(make_poly(
    "Anthony Chabot Regional Park", "Regional Park", "East Bay Regional Park District", 5067,
    "#db2777", "#f472b6", 0.18, None, chabot_coords,
    "Forested eucalyptus and pine ridges above Lake Chabot with extensive hiking, biking, and horse trails."
))

# Del Valle Regional Park (~4,395 acres)
del_valle_coords = [
    [-121.73, 37.64], [-121.66, 37.64], [-121.66, 37.58], [-121.73, 37.58],
    [-121.73, 37.64]
]
features.append(make_poly(
    "Del Valle Regional Park", "Regional Park", "East Bay Regional Park District", 4395,
    "#db2777", "#f472b6", 0.18, None, del_valle_coords,
    "5-mile reservoir in oak hills with warm water swimming, boating, and Ohlone Wilderness Trail trailhead."
))

geojson_payload = {
    "type": "FeatureCollection",
    "features": features
}

with open("park_boundaries.geojson", "w") as f:
    json.dump(geojson_payload, f, indent=2)

print(f"Generated park_boundaries.geojson with {len(features)} park & wilderness boundary polygons!")
