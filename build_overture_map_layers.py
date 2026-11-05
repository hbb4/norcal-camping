#!/usr/bin/env python3
"""
build_overture_map_layers.py

Builds the map overlay datasets used by generate_final_dashboard.py from
Overture Maps (an open, OpenStreetMap-derived dataset published as GeoParquet
on a public S3 bucket):

  park_boundaries.geojson     National Parks, State Parks, Wilderness Areas,
                              National Forests, BLM / USFS units, regional parks
  prominent_trails.geojson    Hiking trails routed along the real trail network
                              (PCT, JMT, Tahoe Rim Trail and ~90 classic hikes)
  prominent_landmarks.geojson Peaks and lakes (snapped to surveyed positions)
  rivers.geojson              River centerlines (merged, simplified)
  rafting_sections.geojson    American River whitewater runs

Usage:
  python3 build_overture_map_layers.py --fetch     # download Overture extracts (~1.1 GB cache)
  python3 build_overture_map_layers.py             # build all layers from cache
  python3 build_overture_map_layers.py boundaries trails   # build selected layers

Requires: pyarrow, shapely, scipy  (pip install pyarrow shapely scipy)
"""

import json
import math
import os
import re
import sys
import time

import pyarrow.dataset as ds
import pyarrow.parquet as pq
import shapely
from shapely import wkb
from shapely.geometry import LineString, MultiLineString, Point, mapping, shape
from shapely.ops import linemerge, substring, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".overture_cache")
OVERTURE_RELEASE = "2026-10-21.0"
REGION_BBOX = (-124.6, 35.2, -117.2, 42.1)  # xmin, ymin, xmax, ymax


# ---------------------------------------------------------------------------
# Fetch (Overture Maps GeoParquet on public S3)
# ---------------------------------------------------------------------------
def _s3_dataset(theme, typ):
    import pyarrow.fs as pafs
    kwargs = dict(anonymous=True, region="us-west-2", connect_timeout=30, request_timeout=180)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        kwargs["proxy_options"] = proxy
    fs = pafs.S3FileSystem(**kwargs)
    path = f"overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme={theme}/type={typ}"
    return ds.dataset(path, filesystem=fs, format="parquet")


def _bbox_filter(xmin, ymin, xmax, ymax):
    F = lambda k: ds.field(("bbox", k))
    return (F("xmin") <= xmax) & (F("xmax") >= xmin) & (F("ymin") <= ymax) & (F("ymax") >= ymin)


def fetch():
    os.makedirs(CACHE, exist_ok=True)
    f = _bbox_filter(*REGION_BBOX)
    jobs = [
        ("land_use.parquet", "base", "land_use",
         ["id", "names", "subtype", "class", "source_tags", "geometry", "bbox", "wikidata"],
         f & ds.field("subtype").isin(["protected", "park", "recreation"])),
        ("land.parquet", "base", "land",
         ["id", "names", "subtype", "class", "elevation", "geometry", "bbox", "wikidata"],
         f & ds.field("class").isin(["peak", "volcano", "saddle", "cliff", "mountain_range", "ridge"])),
        ("water.parquet", "base", "water",
         ["id", "names", "subtype", "class", "geometry", "bbox", "wikidata", "is_intermittent"],
         f & ds.field("subtype").isin(["river", "lake", "reservoir", "stream", "canal", "water"])),
        ("segments.parquet", "transportation", "segment",
         ["id", "names", "class", "subclass", "connectors", "geometry", "bbox"],
         f & (ds.field("subtype") == "road") & ds.field("class").isin(
             ["path", "footway", "bridleway", "track", "steps", "cycleway", "unclassified",
              "residential", "service", "tertiary", "secondary", "living_street", "unknown"])),
    ]
    for fname, theme, typ, cols, flt in jobs:
        t = time.time()
        sc = _s3_dataset(theme, typ).scanner(columns=cols, filter=flt, batch_size=50000)
        writer, n = None, 0
        for b in sc.to_batches():
            if b.num_rows == 0:
                continue
            if writer is None:
                writer = pq.ParquetWriter(os.path.join(CACHE, fname), b.schema)
            writer.write_batch(b)
            n += b.num_rows
        if writer:
            writer.close()
        print(f"  fetched {fname}: {n:,} rows in {time.time() - t:.0f}s")


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------
def rnd(geom, nd=5):
    return shapely.set_precision(geom, 10 ** -nd) if nd else geom


def to_geojson_geom(geom, nd=5):
    g = mapping(geom)

    def r(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], nd), round(c[1], nd)]
        return [r(x) for x in c]

    return {"type": g["type"], "coordinates": r(g["coordinates"])}


def acres_of(geom):
    """Approximate planimetric acreage of a lon/lat polygon."""
    total = 0.0
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for p in polys:
        lat = p.centroid.y
        km2 = p.area * (111.32 ** 2) * math.cos(math.radians(lat))
        total += km2 * 247.105
    return int(round(total, -2)) if total > 1000 else int(round(total))


def length_miles(geom):
    lines = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
    total = 0.0
    for ln in lines:
        c = list(ln.coords)
        for (x1, y1), (x2, y2) in zip(c, c[1:]):
            total += haversine_m(x1, y1, x2, y2)
    return total / 1609.344


def haversine_m(x1, y1, x2, y2):
    R = 6371008.8
    p1, p2 = math.radians(y1), math.radians(y2)
    dp, dl = p2 - p1, math.radians(x2 - x1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def primary_name(names):
    return (names or {}).get("primary") or ""


# ---------------------------------------------------------------------------
# 1. Park, Wilderness & National Forest boundaries
# ---------------------------------------------------------------------------
STYLES = {
    "nps":      dict(color="#0284c7", fillColor="#38bdf8", fillOpacity=0.16, dashArray=None, layer="parks"),
    "csp":      dict(color="#059669", fillColor="#10b981", fillOpacity=0.18, dashArray=None, layer="parks"),
    "wild":     dict(color="#a855f7", fillColor="#c084fc", fillOpacity=0.14, dashArray="6, 6", layer="parks"),
    "blm":      dict(color="#f59e0b", fillColor="#fbbf24", fillOpacity=0.16, dashArray=None, layer="parks"),
    "regional": dict(color="#db2777", fillColor="#f472b6", fillOpacity=0.18, dashArray=None, layer="parks"),
    "forest":   dict(color="#84cc16", fillColor="#65a30d", fillOpacity=0.07, dashArray="2, 5", layer="forests"),
}

# Features kept from the previous official-source build (NPS LRD / CA State Parks
# EnterpriseGIS / Wilderness Connect) because they are already full-resolution.
KEEP_EXISTING = {
    "Yosemite National Park", "Lassen Volcanic National Park", "Marin Headlands (GGNRA)",
    "Point Reyes National Seashore", "Pinnacles National Park", "Desolation Wilderness",
    "Emigrant Wilderness", "John Muir Wilderness", "Mokelumne Wilderness", "Trinity Alps Wilderness",
    "Angel Island State Park", "Bothe-Napa Valley State Park", "Brannan Island State Recreation Area",
    "Calaveras Big Trees State Park", "China Camp State Park", "D.L. Bliss State Park",
    "Donner Memorial State Park", "Emerald Bay State Park", "Half Moon Bay State Beach",
    "Henry Cowell Redwoods State Park", "Henry W. Coe State Park", "Julia Pfeiffer Burns State Park",
    "Mount Tamalpais State Park", "Portola Redwoods State Park", "Russian Gulch State Park",
    "Salt Point State Park", "Samuel P. Taylor State Park", "Sugarloaf Ridge State Park",
    "Van Damme State Park", "Pfeiffer Big Sur State Park", "Castle Crags State Park",
    "Mount Diablo State Park", "Sonoma Coast State Park", "Fremont Peak State Park",
    "Sugar Pine Point State Park", "McArthur-Burney Falls State Park", "Big Basin Redwoods State Park",
    "Butano State Park",
}

# (overture name regex, display name, category, agency, style, description)
# Every regex must match one or more Overture land_use features; matches are unioned.
BOUNDARY_SPECS = [
    # --- National Parks / Monuments / NRAs ---------------------------------------------------
    (r"^Kings Canyon National Park$", "Kings Canyon National Park", "National Park", "National Park Service", "nps",
     "Deepest canyon in North America (8,200 ft): Zumwalt Meadow, Roaring River Falls, Cedar Grove, Grant Grove's General Grant Tree, and the Rae Lakes Loop."),
    (r"^Sequoia National Park$", "Sequoia National Park", "National Park", "National Park Service", "nps",
     "Giant Forest with the General Sherman Tree (largest tree on Earth by volume), Moro Rock, Crystal Cave, Mineral King, and the High Sierra Trail to Mount Whitney."),
    (r"^Redwood National Park$", "Redwood National Park", "National Park", "National Park Service", "nps",
     "Tallest trees on Earth along the Del Norte & Humboldt coast: Tall Trees Grove, Lady Bird Johnson Grove, Gold Bluffs Beach, and Roosevelt elk herds."),
    (r"^Devils Postpile National Monument$", "Devils Postpile National Monument", "National Monument", "National Park Service", "nps",
     "Geometric 60-foot basalt columns and 101-foot Rainbow Falls on the Middle Fork San Joaquin River; JMT and PCT pass through."),
    (r"^Muir Woods National Monument$", "Muir Woods National Monument", "National Monument", "National Park Service", "nps",
     "Old-growth coast redwood cathedral in Redwood Canyon below Mount Tamalpais; timed parking reservations required."),
    (r"^Lava Beds National Monument$", "Lava Beds National Monument", "National Monument", "National Park Service", "nps",
     "Over 700 lava tube caves, cinder cones, and Modoc War history on the Medicine Lake volcano's flank."),
    (r"^Whiskeytown-Shasta-Trinity National Recreation Area - W", "Whiskeytown National Recreation Area", "National Recreation Area", "National Park Service", "nps",
     "Crystal-clear mountain lake ringed by pine forests and multi-tier waterfalls like Whiskeytown Falls and Brandy Creek Falls."),
    (r"^Whiskeytown-Shasta-Trinity National Recreation Area - S", "Shasta Unit (Whiskeytown-Shasta-Trinity NRA)", "National Recreation Area", "US Forest Service (Shasta-Trinity NF)", "blm",
     "California's largest reservoir: 365 miles of shoreline, houseboating, Shasta Caverns, and lakeside USFS campgrounds."),
    (r"^Whiskeytown-Shasta-Trinity National Recreation Area - T", "Trinity Unit (Whiskeytown-Shasta-Trinity NRA)", "National Recreation Area", "US Forest Service (Shasta-Trinity NF)", "blm",
     "Trinity Lake (Clair Engle Lake) beneath the Trinity Alps: quiet coves, boat-in camps, and trailheads into the Trinity Alps Wilderness."),
    (r"^Smith River National Recreation Area$", "Smith River National Recreation Area", "National Recreation Area", "US Forest Service (Six Rivers NF)", "blm",
     "California's last major undammed river system: emerald-green pools, old-growth redwoods, and wild & scenic river corridors."),
    (r"^Giant Sequoia National Monument$", "Giant Sequoia National Monument", "National Monument", "US Forest Service (Sequoia NF)", "blm",
     "33 giant sequoia groves surrounding Sequoia & Kings Canyon NPs, including the Trail of 100 Giants and Hume Lake."),
    (r"^Berryessa Snow Mountain National Monument$", "Berryessa Snow Mountain National Monument", "National Monument", "BLM / US Forest Service", "blm",
     "Inner Coast Range wildlands from Lake Berryessa to Snow Mountain: tule elk, bald eagles, Cache Creek, and serpentine wildflowers."),
    (r"^Fort Ord National Monument$", "Fort Ord National Monument", "National Monument", "Bureau of Land Management (BLM)", "blm",
     "86 miles of oak-woodland and maritime chaparral trails above Monterey Bay; world-class mountain biking (Sea Otter Classic)."),
    (r"^Alabama Hills National Scenic Area$", "Alabama Hills National Scenic Area", "National Scenic Area", "Bureau of Land Management (BLM)", "blm",
     "World-famous golden granite rock arches and rounded labyrinth boulders directly beneath snow-capped Mount Whitney."),

    # --- Wilderness Areas ----------------------------------------------------------------------
    (r"^Ventana Wilderness$", "Ventana Wilderness", "National Wilderness Area", "US Forest Service (Los Padres NF)", "wild",
     "Steep coastal Santa Lucia Mountains, Sykes Hot Springs, Big Sur headwaters, and deep redwood canyons."),
    (r"^Silver Peak Wilderness$", "Silver Peak Wilderness", "National Wilderness Area", "US Forest Service (Los Padres NF)", "wild",
     "Southern Big Sur's wildest coast range: Salmon Creek Falls, the southernmost coast redwoods, and Cruickshank camp."),
    (r"^Ansel Adams Wilderness$", "Ansel Adams Wilderness", "National Wilderness Area", "US Forest Service (Inyo/Sierra NF)", "wild",
     "Dramatic Ritter Range, Minarets, Banner Peak, Thousand Island Lake, and the famed John Muir Trail."),
    (r"^Yosemite Wilderness$", "Yosemite Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "95% of Yosemite National Park: Grand Canyon of the Tuolumne, Cathedral Range, Clark Range, and 750+ miles of trail (permits required)."),
    (r"^Sequoia-Kings Canyon Wilderness$", "Sequoia-Kings Canyon Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "768,000-acre High Sierra core: Evolution Basin, Rae Lakes, Sixty Lake Basin, the Great Western Divide, and the Kern Canyon."),
    (r"^John Krebs Wilderness$", "John Krebs Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "Mineral King valley and its glacial lakes (Monarch, Eagle, White Chief, Franklin) in southern Sequoia National Park."),
    (r"^Monarch Wilderness$", "Monarch Wilderness", "National Wilderness Area", "US Forest Service (Sierra/Sequoia NF)", "wild",
     "Rugged, trail-sparse walls of the Kings River canyon between Kings Canyon NP and Hume Lake."),
    (r"^Jennie Lakes Wilderness$", "Jennie Lakes Wilderness", "National Wilderness Area", "US Forest Service (Sequoia NF)", "wild",
     "Compact granite-lake wilderness bordering Sequoia NP; easy overnight to Jennie and Weaver Lakes from Big Meadows."),
    (r"^Golden Trout Wilderness$", "Golden Trout Wilderness", "National Wilderness Area", "US Forest Service (Inyo/Sequoia NF)", "wild",
     "Home waters of California's state fish along the Little Kern and South Fork Kern; Cottonwood Lakes and Kern Plateau meadows."),
    (r"^South Sierra Wilderness$", "South Sierra Wilderness", "National Wilderness Area", "US Forest Service (Inyo/Sequoia NF)", "wild",
     "Southern Sierra crest along the PCT: Olancha Peak, Monache Meadows, and the South Fork Kern River."),
    (r"^Dinkey Lakes Wilderness$", "Dinkey Lakes Wilderness", "National Wilderness Area", "US Forest Service (Sierra NF)", "wild",
     "Sixteen small granite lakes and the Three Sisters above Courtright Reservoir; gentle loop backpacking."),
    (r"^Kaiser Wilderness$", "Kaiser Wilderness", "National Wilderness Area", "US Forest Service (Sierra NF)", "wild",
     "Kaiser Ridge above Huntington Lake with panoramic views of the Ritter Range and Mount Ritter."),
    (r"^Owens River Headwaters Wilderness$", "Owens River Headwaters Wilderness", "National Wilderness Area", "US Forest Service (Inyo NF)", "wild",
     "Glass Creek Meadow and the San Joaquin Ridge headwaters of the Owens River north of Mammoth Mountain."),
    (r"^Hoover Wilderness$", "Hoover Wilderness", "National Wilderness Area", "US Forest Service (Humboldt-Toiyabe/Inyo NF)", "wild",
     "Sawtooth Ridge, Twenty Lakes Basin, and Green Creek on the east side of Yosemite."),
    (r"^Carson-Iceberg Wilderness$", "Carson-Iceberg Wilderness", "National Wilderness Area", "US Forest Service (Stanislaus/Humboldt-Toiyabe NF)", "wild",
     "Volcanic Dardanelles, the Iceberg granite dome, and Carson River headwaters along the PCT between Ebbetts and Sonora Passes."),
    (r"^Granite Chief Wilderness$", "Granite Chief Wilderness", "National Wilderness Area", "US Forest Service (Tahoe NF)", "wild",
     "Headwaters of the American River west of Palisades Tahoe, crossed by the PCT and the Tahoe Rim Trail."),
    (r"^Mount Rose Wilderness$", "Mount Rose Wilderness", "National Wilderness Area", "US Forest Service (Humboldt-Toiyabe NF)", "wild",
     "Highest point in the Tahoe Basin rim's northern half: Mount Rose (10,776 ft), Galena Falls, and Relay Peak on the Tahoe Rim Trail."),
    (r"^Bucks Lake Wilderness$", "Bucks Lake Wilderness", "National Wilderness Area", "US Forest Service (Plumas NF)", "wild",
     "Spanish Peak and the Feather River canyon rim along the PCT above Bucks Lake."),
    (r"^Caribou Wilderness$", "Caribou Wilderness", "National Wilderness Area", "US Forest Service (Lassen NF)", "wild",
     "Gentle volcanic plateau dotted with 20+ forested lakes east of Lassen Volcanic NP."),
    (r"^Thousand Lakes Wilderness$", "Thousand Lakes Wilderness", "National Wilderness Area", "US Forest Service (Lassen NF)", "wild",
     "Glacial basin of Magee Peak and Crater Peak north of Lassen; Lake Eiler and the Thousand Lakes Valley."),
    (r"^Lassen Volcanic Wilderness$", "Lassen Volcanic Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "Backcountry of Lassen Volcanic NP: Cinder Cone, Snag Lake, the Painted Dunes, and Juniper Lake."),
    (r"^Ishi Wilderness$", "Ishi Wilderness", "National Wilderness Area", "US Forest Service (Lassen NF)", "wild",
     "Low-elevation basalt canyons of Mill and Deer Creeks; best in spring wildflower season."),
    (r"^Mount Shasta Wilderness$", "Mount Shasta Wilderness", "National Wilderness Area", "US Forest Service (Shasta-Trinity NF)", "wild",
     "The 14,179-ft stratovolcano and its seven glaciers; Avalanche Gulch, Casaval Ridge, and Clear Creek climbing routes."),
    (r"^Castle Crags Wilderness$", "Castle Crags Wilderness", "National Wilderness Area", "US Forest Service (Shasta-Trinity NF)", "wild",
     "Granite spires above Castle Crags State Park; the PCT traverses the base of the crags."),
    (r"^Russian Wilderness$", "Russian Wilderness", "National Wilderness Area", "US Forest Service (Klamath NF)", "wild",
     "Compact granite cirque-lake country along the PCT between the Trinity Alps and Marble Mountains."),
    (r"^Marble Mountain Wilderness$", "Marble Mountain Wilderness", "National Wilderness Area", "US Forest Service (Klamath NF)", "wild",
     "Marble-capped peaks, 89 trout lakes, and the PCT along the Marble Rim in the Klamath Mountains."),
    (r"^Siskiyou Wilderness$", "Siskiyou Wilderness", "National Wilderness Area", "US Forest Service (Six Rivers/Klamath NF)", "wild",
     "Remote Siskiyou crest with Preston Peak, Clear Creek, and exceptional conifer diversity."),
    (r"^Red Buttes Wilderness$", "Red Buttes Wilderness", "National Wilderness Area", "US Forest Service (Klamath/Rogue River-Siskiyou NF)", "wild",
     "Serpentine-red peaks straddling the Oregon border along the PCT."),
    (r"^Yolla Bolly-Middle Eel Wilderness$", "Yolla Bolly-Middle Eel Wilderness", "National Wilderness Area", "US Forest Service (Mendocino/Shasta-Trinity NF)", "wild",
     "Northern Coast Range high country: Solomon Peak, Mount Linn, and the Middle Fork Eel headwaters."),
    (r"^Snow Mountain Wilderness$", "Snow Mountain Wilderness", "National Wilderness Area", "US Forest Service (Mendocino NF)", "wild",
     "Twin 7,000-ft summits of Snow Mountain, the highest point of the inner Coast Range near Clear Lake."),
    (r"^Yuki Wilderness$", "Yuki Wilderness", "National Wilderness Area", "US Forest Service / BLM", "wild",
     "Rugged Eel River canyon country of the Mendocino National Forest."),
    (r"^Sanhedrin Wilderness$", "Sanhedrin Wilderness", "National Wilderness Area", "US Forest Service (Mendocino NF)", "wild",
     "Sanhedrin Mountain ridge and Eel River tributaries above Lake Pillsbury."),
    (r"^Cache Creek Wilderness$", "Cache Creek Wilderness", "National Wilderness Area", "Bureau of Land Management (BLM)", "wild",
     "Cache Creek canyon and Blue Ridge: wintering bald eagles, tule elk, and whitewater in spring."),
    (r"^King Range Wilderness$", "King Range Wilderness", "National Wilderness Area", "Bureau of Land Management (BLM)", "wild",
     "California's Lost Coast: 25 miles of roadless beach trail beneath 4,000-ft King Peak (tide-dependent)."),
    (r"^Sinkyone Wilderness State Park$|^Sinkyone State Wilderness$", "Sinkyone Wilderness State Park", "State Wilderness", "California State Parks", "wild",
     "Southern Lost Coast: Usal Beach, Bear Harbor, and the Lost Coast Trail through redwood and prairie headlands."),
    (r"^Phillip Burton Wilderness$", "Phillip Burton Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "Point Reyes wilderness: Wildcat Camp, Alamere Falls, Bear Valley, and Inverness Ridge."),
    (r"^Hain Wilderness$", "Hain Wilderness", "National Wilderness Area", "National Park Service", "wild",
     "Pinnacles' volcanic High Peaks and Chalone Peak backcountry; California condor habitat."),
    (r"^South Warner Wilderness$", "South Warner Wilderness", "National Wilderness Area", "US Forest Service (Modoc NF)", "wild",
     "Remote northeast California crest: Eagle Peak (9,892 ft) and the Summit Trail."),
    (r"^Domeland Wilderness$", "Domeland Wilderness", "National Wilderness Area", "US Forest Service (Sequoia NF) / BLM", "wild",
     "Granite domes above the South Fork Kern River on the southern Sierra Kern Plateau; PCT crosses its eastern edge."),
    (r"^Inyo Mountains Wilderness$", "Inyo Mountains Wilderness", "National Wilderness Area", "US Forest Service / BLM", "wild",
     "Steep desert range rising 10,000 ft above Owens Valley opposite the Sierra crest."),
    (r"^White Mountains Wilderness$", "White Mountains Wilderness", "National Wilderness Area", "US Forest Service / BLM", "wild",
     "White Mountain Peak (14,252 ft) and the Ancient Bristlecone Pine Forest region."),
    (r"^Santa Lucia Wilderness$", "Santa Lucia Wilderness", "National Wilderness Area", "US Forest Service (Los Padres NF)", "wild",
     "Lopez Canyon and Big Falls in the southern Santa Lucia Range near San Luis Obispo."),
    (r"^Garcia Wilderness$", "Garcia Wilderness", "National Wilderness Area", "US Forest Service (Los Padres NF)", "wild",
     "Chaparral ridges of Garcia Mountain above the upper Salinas River."),
    (r"^Machesna Mountain Wilderness$", "Machesna Mountain Wilderness", "National Wilderness Area", "US Forest Service / BLM", "wild",
     "Rugged La Panza Range chaparral and condor flyways east of Santa Margarita."),
    (r"^Mount Lassic Wilderness$", "Mount Lassic Wilderness", "National Wilderness Area", "US Forest Service (Six Rivers NF)", "wild",
     "Mount Lassic's twin rocky summits and serpentine barrens in the southern Six Rivers NF."),
    (r"^North Fork Wilderness$", "North Fork Wilderness", "National Wilderness Area", "US Forest Service (Six Rivers NF)", "wild",
     "Deep, trail-less canyon of the North Fork Eel River."),
    (r"^Chanchelulla Wilderness$", "Chanchelulla Wilderness", "National Wilderness Area", "US Forest Service (Shasta-Trinity NF)", "wild",
     "Chanchelulla Peak and old-growth fir forest south of Hayfork."),
    (r"^Elkhorn Ridge Wilderness$", "Elkhorn Ridge Wilderness", "National Wilderness Area", "Bureau of Land Management (BLM)", "wild",
     "Douglas-fir and oak ridges above the South Fork Eel River."),
    (r"^South Fork Eel River Wilderness$", "South Fork Eel River Wilderness", "National Wilderness Area", "Bureau of Land Management (BLM)", "wild",
     "Angelo Coast Range Reserve neighbor: old-growth Douglas-fir along the South Fork Eel."),
    (r"^Cedar Roughs Wilderness$", "Cedar Roughs Wilderness", "National Wilderness Area", "Bureau of Land Management (BLM)", "wild",
     "Rare Sargent cypress stands on serpentine ridges west of Lake Berryessa."),

    # --- State Parks not covered by the official CSP layer above -------------------------------
    (r"^Humboldt Redwoods State Park$", "Humboldt Redwoods State Park", "State Park", "California State Parks", "csp",
     "World's largest remaining old-growth coast redwood forest: Avenue of the Giants, Rockefeller Forest, and Founders Grove."),
    (r"^Prairie Creek Redwoods State Park$", "Prairie Creek Redwoods State Park", "State Park", "California State Parks", "csp",
     "Fern Canyon, Gold Bluffs Beach, Elk Prairie herds, and the James Irvine Trail through towering redwoods."),
    (r"^Jedediah Smith Redwoods State Park$", "Jedediah Smith Redwoods State Park", "State Park", "California State Parks", "csp",
     "Stout Grove and the emerald Smith River; Howland Hill Road and Boy Scout Tree Trail."),
    (r"^Del Norte Coast Redwoods State Park$", "Del Norte Coast Redwoods State Park", "State Park", "California State Parks", "csp",
     "Redwoods plunging to the sea at Damnation Creek and Mill Creek Campground."),
    (r"^Mendocino Headlands State Park$", "Mendocino Headlands State Park", "State Park", "California State Parks", "csp",
     "Blufftop sea arches and blowholes encircling historic Mendocino village."),
    (r"^Hendy Woods State Park$", "Hendy Woods State Park", "State Park", "California State Parks", "csp",
     "Big Hendy and Little Hendy old-growth redwood groves along the Navarro River in Anderson Valley."),
    (r"^Clear Lake State Park$", "Clear Lake State Park", "State Park", "California State Parks", "csp",
     "Lakeside camping on California's largest natural freshwater lake beneath Mount Konocti."),
    (r"^Austin Creek State Recreation Area$|^Armstrong Redwoods State Natural Reserve$", "Armstrong Redwoods SNR & Austin Creek SRA", "State Park", "California State Parks", "csp",
     "Colonel Armstrong's 1,400-year-old redwoods and the oak-studded ridges of Austin Creek above Guerneville (Bullfrog Pond camp)."),
    (r"^New Brighton State Beach$", "New Brighton State Beach", "State Beach", "California State Parks", "csp",
     "Blufftop campground above Monterey Bay in Capitola; Monarch butterfly overwintering."),
    (r"^Sunset State Beach$", "Sunset State Beach", "State Beach", "California State Parks", "csp",
     "Wide dune-backed beach on southern Monterey Bay with pine-sheltered campsites."),
    (r"^San Luis Reservoir State Recreation Area$", "San Luis Reservoir State Recreation Area", "State Recreation Area", "California State Parks", "csp",
     "Pacheco Pass reservoir with Basalt and Medeiros campgrounds, windsurfing, and striped bass."),
    (r"^Mono Lake Tufa State Natural Reserve$", "Mono Lake Tufa State Natural Reserve", "State Natural Reserve", "California State Parks", "csp",
     "Otherworldly tufa towers on the shores of the ancient saline Mono Lake; South Tufa boardwalk and Navy Beach."),
    (r"^Andrew Molera State Park$", "Andrew Molera State Park", "State Park", "California State Parks", "csp",
     "Big Sur River mouth, walk-in trail camp, and the Bluffs/Panorama/Ridge loop."),
    (r"^Limekiln State Park$", "Limekiln State Park", "State Park", "California State Parks", "csp",
     "Redwood canyon with 1880s lime kilns, a 100-ft waterfall, and beach camping on the Big Sur coast."),
    (r"^Castle Rock State Park$", "Castle Rock State Park", "State Park", "California State Parks", "csp",
     "Wind-sculpted sandstone outcrops and Castle Rock Falls on the Skyline crest of the Santa Cruz Mountains."),
    (r"^Grover Hot Springs State Park$", "Grover Hot Springs State Park", "State Park", "California State Parks", "csp",
     "Hot springs pools in a Sierra meadow at the foot of Markleeville; trail to Burnside Lake falls."),
    (r"^Plumas-Eureka State Park$", "Plumas-Eureka State Park", "State Park", "California State Parks", "csp",
     "Historic gold-mining stamp mill, Eureka Peak, and lakes of the Lakes Basin near Graeagle."),
    (r"^Trione-Annadel State Park$", "Trione-Annadel State Park", "State Park", "California State Parks", "csp",
     "40 miles of singletrack and Lake Ilsanjo in the hills above Santa Rosa."),
    (r"^Point Lobos State Natural Reserve$", "Point Lobos State Natural Reserve", "State Natural Reserve", "California State Parks", "csp",
     "\"Greatest meeting of land and water in the world\": Cypress Grove, China Cove, sea otters, and harbor seals."),
    (r"^Spooner Lake & Backcountry State Park$|^Sand Harbor Beach State Recreation Area$", "Lake Tahoe-Nevada State Park", "State Park (NV)", "Nevada State Parks", "csp",
     "Sand Harbor crystal-turquoise boulder coves, Spooner Lake cross-country ski trails, and the famed Marlette Flume Trail."),

    # --- County & Regional Parks (previously 5-point placeholders) -----------------------------
    (r"^Mount Madonna County Park$", "Mount Madonna County Park", "County Park", "Santa Clara County Parks", "regional",
     "Coast redwood forest on the mountain ridge between Gilroy and Watsonville; canvas yurts and white deer sanctuary."),
    (r"^Sanborn County Park$", "Sanborn County Park", "County Park", "Santa Clara County Parks", "regional",
     "Lush redwood forest above Saratoga with direct trail connection to Castle Rock State Park sandstone spires."),
    (r"^Uvas Canyon County Park$", "Uvas Canyon County Park", "County Park", "Santa Clara County Parks", "regional",
     "Lush waterfall canyon featuring six cascading multi-tier natural waterfalls along Swanson Creek."),
    (r"^Memorial County Park$", "Memorial County Park", "County Park", "San Mateo County Parks", "regional",
     "Historic coast redwood park along Pescadero Creek with natural swimming holes and Mt. Ellen trail."),
    (r"^Anthony Chabot Regional Park$|^Lake Chabot Regional Park$", "Anthony Chabot Regional Park", "Regional Park", "East Bay Regional Park District", "regional",
     "Forested eucalyptus and pine ridges above Lake Chabot with extensive hiking, biking, and horse trails."),
    (r"^Del Valle Regional Park$", "Del Valle Regional Park", "Regional Park", "East Bay Regional Park District", "regional",
     "5-mile reservoir in oak hills with warm water swimming, boating, and Ohlone Wilderness Trail trailhead."),
    (r"^Sunol Regional Wilderness$|^Ohlone Regional Wilderness", "Sunol-Ohlone Regional Wilderness", "Regional Wilderness", "East Bay Regional Park District", "regional",
     "Little Yosemite gorge, Mission Peak backside, and the 28-mile Ohlone Wilderness Trail backpacking route (permit required)."),

    # --- National Forests (separate toggleable layer) -----------------------------------------
    (r"^Klamath National Forest$", "Klamath National Forest", "National Forest", "US Forest Service", "forest",
     "1.7 million acres of the Klamath Mountains: Marble Mountain & Russian Wildernesses, Scott and Salmon River canyons."),
    (r"^Six Rivers National Forest$", "Six Rivers National Forest", "National Forest", "US Forest Service", "forest",
     "Smith, Klamath, Trinity, Mad, Van Duzen and Eel River country inland from the redwood coast."),
    (r"^Shasta-Trinity National Forest$", "Shasta-Trinity National Forest", "National Forest", "US Forest Service", "forest",
     "California's largest national forest: Mount Shasta, the Trinity Alps, Shasta & Trinity Lakes."),
    (r"^Modoc National Forest$", "Modoc National Forest", "National Forest", "US Forest Service", "forest",
     "Northeast California's volcanic plateau, Medicine Lake Highlands, and the South Warner Mountains."),
    (r"^Lassen National Forest$", "Lassen National Forest", "National Forest", "US Forest Service", "forest",
     "Surrounds Lassen Volcanic NP: Caribou, Thousand Lakes, and Ishi Wildernesses; Hat Creek and Lake Almanor."),
    (r"^Plumas National Forest$", "Plumas National Forest", "National Forest", "US Forest Service", "forest",
     "Feather River canyons, Lakes Basin, Bucks Lake, and Feather Falls (410 ft)."),
    (r"^Tahoe National Forest$", "Tahoe National Forest", "National Forest", "US Forest Service", "forest",
     "North Yuba and American River headwaters: Sierra Buttes, Donner Summit, and Granite Chief Wilderness."),
    (r"^Lake Tahoe Basin Management Unit$", "Lake Tahoe Basin Management Unit", "National Forest", "US Forest Service", "forest",
     "USFS lands ringing Lake Tahoe: Desolation Wilderness gateways, Tahoe Rim Trail, and lakeshore campgrounds."),
    (r"^Eldorado National Forest$", "Eldorado National Forest", "National Forest", "US Forest Service", "forest",
     "Crystal Basin, Desolation & Mokelumne Wildernesses, Carson Pass, and the South Fork American River."),
    (r"^Stanislaus National Forest$", "Stanislaus National Forest", "National Forest", "US Forest Service", "forest",
     "Emigrant & Carson-Iceberg Wildernesses, Pinecrest Lake, Sonora Pass, and the Tuolumne River gorge."),
    (r"^Sierra National Forest$", "Sierra National Forest", "National Forest", "US Forest Service", "forest",
     "Between Yosemite and Kings Canyon: Huntington Lake, Shaver Lake, Ansel Adams, Kaiser, and Dinkey Lakes Wildernesses."),
    (r"^Inyo National Forest$", "Inyo National Forest", "National Forest", "US Forest Service", "forest",
     "Eastern Sierra crest: Mount Whitney, Mammoth Lakes, June Lake Loop, Big Pine Creek, and the Ancient Bristlecone Pine Forest."),
    (r"^Sequoia National Forest$", "Sequoia National Forest", "National Forest", "US Forest Service", "forest",
     "Giant Sequoia NM, Kern River canyon, Golden Trout & Domeland Wildernesses, and Hume Lake."),
    (r"^Mendocino National Forest$", "Mendocino National Forest", "National Forest", "US Forest Service", "forest",
     "The only national forest in California with no paved highway crossing: Snow Mountain, Lake Pillsbury, Yolla Bolly."),
    (r"^Los Padres National Forest$", "Los Padres National Forest", "National Forest", "US Forest Service", "forest",
     "Big Sur's Santa Lucia Range (Ventana & Silver Peak Wildernesses) south through the Transverse Ranges."),
    (r"^Humboldt.Toiyabe National Forest$", "Humboldt-Toiyabe National Forest (CA districts)", "National Forest", "US Forest Service", "forest",
     "Bridgeport and Carson Ranger Districts on the eastern Sierra: Hoover Wilderness, Twin Lakes, and Sonora/Monitor Passes."),
]

# Simplification tolerance (degrees) by size; ~0.0002 deg is ~20 m.
def _simplify_tol(geom):
    a = geom.area
    if a > 0.15:
        return 0.0006
    if a > 0.03:
        return 0.00035
    if a > 0.005:
        return 0.0002
    return 0.00006


def _clip_ca_portion(geom):
    """Trim huge multi-state forests to the map region (keeps CA districts of Humboldt-Toiyabe)."""
    from shapely.geometry import box
    return geom.intersection(box(-120.2, 38.0, -119.0, 39.5))


def build_boundaries():
    rows = pq.read_table(os.path.join(CACHE, "land_use.parquet"),
                         columns=["id", "names", "subtype", "class", "source_tags", "geometry"],
                         filters=ds.field("subtype") == "protected").to_pylist()
    rows += pq.read_table(os.path.join(CACHE, "land_use.parquet"),
                          columns=["id", "names", "subtype", "class", "source_tags", "geometry"],
                          filters=ds.field("class") == "park").to_pylist()
    by_name = {}
    for r in rows:
        by_name.setdefault(primary_name(r["names"]), []).append(r)

    old = json.load(open(os.path.join(HERE, "park_boundaries.geojson")))
    old_feats = {f["properties"]["name"]: f for f in old["features"]}

    out = []
    for name in KEEP_EXISTING:
        f = old_feats[name]
        st = "nps" if "National" in f["properties"]["category"] and "Wilderness" not in f["properties"]["category"] else (
            "wild" if "Wilderness" in f["properties"]["category"] else "csp")
        f["properties"]["layer"] = STYLES[st]["layer"]
        f["properties"]["source"] = "Official agency GIS (NPS LRD / CSP EnterpriseGIS / Wilderness Connect)"
        out.append(f)

    for pattern, disp, cat, agency, style, desc in BOUNDARY_SPECS:
        rx = re.compile(pattern)
        polys = []
        for nm, rs in by_name.items():
            if rx.search(nm):
                for r in rs:
                    g = wkb.loads(r["geometry"])
                    if g.geom_type in ("Polygon", "MultiPolygon") and g.area > 0:
                        polys.append(shapely.make_valid(g))
        if not polys:
            print(f"  !! no Overture geometry for {disp} ({pattern})")
            continue
        geom = unary_union(polys)
        if disp.startswith("Humboldt-Toiyabe"):
            geom = _clip_ca_portion(geom)
        acres = acres_of(geom)
        geom = geom.simplify(_simplify_tol(geom), preserve_topology=True)
        geom = shapely.make_valid(rnd(geom))
        if geom.geom_type == "GeometryCollection":
            geom = unary_union([g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")])
        # drop tiny slivers
        if geom.geom_type == "MultiPolygon":
            keep = [p for p in geom.geoms if p.area > 2e-7]
            geom = shapely.MultiPolygon(keep) if len(keep) > 1 else keep[0]
        props = {"name": disp, "category": cat, "agency": agency, "acres": acres, **STYLES[style],
                 "description": desc, "source": "OpenStreetMap via Overture Maps"}
        out.append({"type": "Feature", "properties": props, "geometry": to_geojson_geom(geom)})

    # Drawing order: forests underneath, then wilderness, then monuments/BLM, NPS, state, regional.
    order = {"National Forest": 0}
    def rank(f):
        p = f["properties"]
        if p["layer"] == "forests":
            return 0
        if "Wilderness" in p["category"] and p["agency"] != "East Bay Regional Park District":
            return 1
        if p["color"] == "#f59e0b":
            return 2
        if p["color"] == "#0284c7":
            return 3
        if p["color"] == "#059669":
            return 4
        return 5
    out.sort(key=lambda f: (rank(f), -(f["properties"].get("acres") or 0)))

    with open(os.path.join(HERE, "park_boundaries.geojson"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": out}, fh, separators=(",", ":"))
    print(f"  park_boundaries.geojson: {len(out)} features, "
          f"{os.path.getsize(os.path.join(HERE, 'park_boundaries.geojson')) / 1e6:.1f} MB")


# ---------------------------------------------------------------------------
# 2. Trail router (shortest path over the OSM trail network, via Overture)
# ---------------------------------------------------------------------------
HALFMILE_PCT_URL = ("https://raw.githubusercontent.com/andrewtpham/disha-trails/main/"
                    "trails/pct/pacific-crest-trail.geojson")
JMT_GUIDE_URL = ("https://raw.githubusercontent.com/CGodiksen/walk-the-world/main/"
                 "web/public/data/routes/john-muir-trail.geojson")

CLASS_COST = {
    "path": 1.0, "footway": 1.0, "bridleway": 1.0, "steps": 1.0,
    "track": 1.35, "cycleway": 1.6,
    "unknown": 2.2, "service": 2.6, "unclassified": 2.6, "living_street": 2.6, "residential": 3.0,
    "tertiary": 4.0, "secondary": 5.0,
}
TRAIL_CLASSES = {"path", "footway", "bridleway", "steps", "track"}


def _download_cached(url, fname):
    import urllib.request
    path = os.path.join(CACHE, fname)
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as fh:
            fh.write(r.read())
    return json.load(open(path))


class TrailNetwork:
    """Loads Overture trail/road segments for a bbox and routes over them."""

    _dataset = None

    def __init__(self, bbox, name_re=None):
        import numpy as np
        from scipy.spatial import cKDTree
        if TrailNetwork._dataset is None:
            TrailNetwork._dataset = ds.dataset(os.path.join(CACHE, "segments.parquet"), format="parquet")
        tb = TrailNetwork._dataset.to_table(columns=["names", "class", "subclass", "geometry"],
                                            filter=_bbox_filter(*bbox))
        names = tb.column("names").to_pylist()
        classes = tb.column("class").to_pylist()
        subclasses = tb.column("subclass").to_pylist()
        geoms = tb.column("geometry").to_pylist()
        self.name_re = re.compile(name_re, re.I) if name_re else None

        node_id, coords = {}, []
        rows, cols, wts = [], [], []
        self.named_nodes = set()
        self.trail_nodes = set()

        def nid(pt):
            k = (round(pt[0], 6), round(pt[1], 6))
            i = node_id.get(k)
            if i is None:
                i = node_id[k] = len(coords)
                coords.append(k)
            return i

        for nm, cl, sc, gb in zip(names, classes, subclasses, geoms):
            if sc in ("sidewalk", "crosswalk", "parking_aisle", "driveway", "drive_through"):
                continue
            base = CLASS_COST.get(cl, 3.0)
            name = primary_name(nm)
            match = bool(self.name_re and name and self.name_re.search(name))
            factor = base * (0.35 if match else 1.0)
            pts = list(wkb.loads(gb).coords)
            ids = [nid(p) for p in pts]
            for (a, pa), (b, pb) in zip(zip(ids, pts), zip(ids[1:], pts[1:])):
                if a == b:
                    continue
                w = haversine_m(pa[0], pa[1], pb[0], pb[1]) * factor
                rows += [a, b]
                cols += [b, a]
                wts += [w, w]
            if match:
                self.named_nodes.update(ids)
            if cl in TRAIL_CLASSES:
                self.trail_nodes.update(ids)

        from scipy.sparse import csr_matrix
        n = len(coords)
        self.coords = np.array(coords) if coords else np.zeros((0, 2))
        self.graph = csr_matrix((wts, (rows, cols)), shape=(n, n))
        self.lat0 = (bbox[1] + bbox[3]) / 2
        self.kx = math.cos(math.radians(self.lat0))
        scaled = self.coords * [self.kx, 1.0]
        self.tree = cKDTree(scaled)
        self._subtrees = {}
        # Connected components: every trail's waypoints must snap into one common component.
        from scipy.sparse.csgraph import connected_components
        if n:
            _, self.labels = connected_components(self.graph, directed=False)
        else:
            self.labels = np.zeros(0, dtype=int)
        self.named_nodes = sorted(self.named_nodes)
        self.trail_nodes = sorted(self.trail_nodes)

    def _subtree(self, key, nodes):
        from scipy.spatial import cKDTree
        import numpy as np
        if key not in self._subtrees:
            idx = np.array(nodes, dtype=int)
            self._subtrees[key] = (idx, cKDTree(self.coords[idx] * [self.kx, 1.0]) if len(idx) else None)
        return self._subtrees[key]

    def _snap_in(self, lon, lat, comp, prefer_named=True):
        """Nearest node inside component `comp`, preferring name-matching then trail nodes."""
        import numpy as np
        q = (lon * self.kx, lat)
        tiers = []
        if prefer_named:
            tiers.append(("named", self.named_nodes, 350))
        tiers += [("trail", self.trail_nodes, 700), ("all", None, 1e9)]
        for tier, nodes, lim in tiers:
            key = (tier, comp)
            if key not in self._subtrees:
                pool = np.nonzero(self.labels == comp)[0] if nodes is None else \
                    np.array([i for i in nodes if self.labels[i] == comp], dtype=int)
                self._subtree(key, pool)
            idx, tree = self._subtrees[key]
            if tree is None:
                continue
            d, i = tree.query(q)
            if d * 111_000 <= lim:
                return int(idx[i]), d * 111_000
        return None, float("inf")

    def snap_all(self, waypoints, prefer_named=True):
        import numpy as np
        cands = set()
        for x, y in waypoints:
            for i in self.tree.query((x * self.kx, y), k=min(40, len(self.coords)))[1]:
                cands.add(int(self.labels[i]))
        best = None
        for comp in cands:
            snaps = [self._snap_in(x, y, comp, prefer_named) for x, y in waypoints]
            worst = max(d for _, d in snaps)
            if best is None or worst < best[0]:
                best = (worst, snaps)
        return best[1]

    def route(self, waypoints, prefer_named=True):
        from scipy.sparse.csgraph import dijkstra
        snapped = self.snap_all(waypoints, prefer_named=prefer_named)
        path_nodes = []
        for (a, _), (b, _) in zip(snapped, snapped[1:]):
            if a == b:
                continue
            dist, pred = dijkstra(self.graph, directed=False, indices=a, return_predecessors=True)
            if not math.isfinite(dist[b]):
                return None, snapped, 0.0
            seq = [b]
            while seq[-1] != a:
                seq.append(pred[seq[-1]])
            seq.reverse()
            if path_nodes and path_nodes[-1] == seq[0]:
                seq = seq[1:]
            path_nodes += seq
        coords = [tuple(self.coords[i]) for i in path_nodes]
        named = set(self.named_nodes)
        named_frac = (sum(1 for i in path_nodes if i in named) / len(path_nodes)) if path_nodes else 0
        return (LineString(coords) if len(coords) > 1 else None), snapped, named_frac


def _label_point(poly):
    """Visual center of a (multi)polygon: pole of inaccessibility of its largest part."""
    from shapely.ops import polylabel
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda p: p.area)
    try:
        return polylabel(poly, tolerance=0.0005)
    except Exception:
        return poly.representative_point()


class FeatureLookup:
    """Named peaks (Overture land) and lakes (Overture water) for snapping waypoints/labels."""

    def __init__(self):
        self.peaks = []
        tb = pq.read_table(os.path.join(CACHE, "land.parquet"),
                           columns=["names", "class", "elevation", "geometry"]).to_pylist()
        for r in tb:
            n = primary_name(r["names"])
            if n and r["class"] in ("peak", "volcano"):
                g = wkb.loads(r["geometry"])
                if g.geom_type == "Point":
                    self.peaks.append((self.norm(n), n, g.x, g.y, r["elevation"]))
        self.lakes = []
        wt = pq.read_table(os.path.join(CACHE, "water.parquet"),
                           columns=["names", "subtype", "class", "geometry"],
                           filters=ds.field("subtype").isin(["lake", "reservoir", "water"]))
        names = wt.column("names").to_pylist()
        geoms = wt.column("geometry").to_pylist()
        for nm, gb in zip(names, geoms):
            n = primary_name(nm)
            if n:
                g = wkb.loads(gb)
                if g.geom_type in ("Polygon", "MultiPolygon"):
                    self.lakes.append((self.norm(n), n, g))

    @staticmethod
    def norm(n):
        n = n.lower().replace("mt. ", "mount ").replace("mt ", "mount ").replace("saint ", "st ").replace("st. ", "st ")
        return re.sub(r"[^a-z0-9 ]", "", n).strip()

    def peak(self, name, lon, lat, max_km=12):
        key = self.norm(name)
        best = None
        for k, n, x, y, e in self.peaks:
            if k == key:
                d = haversine_m(lon, lat, x, y)
                if d < max_km * 1000 and (best is None or d < best[0]):
                    best = (d, x, y, e, n)
        return best

    def lake(self, name, lon, lat, max_km=12):
        key = self.norm(name)
        best = None
        for k, n, g in self.lakes:
            if k == key:
                c = _label_point(g)
                d = haversine_m(lon, lat, c.x, c.y)
                if d < max_km * 1000 and (best is None or d < best[0]):
                    best = (d, c.x, c.y, g, n)
        return best


_LOOKUP = None


def lookup():
    global _LOOKUP
    if _LOOKUP is None:
        _LOOKUP = FeatureLookup()
    return _LOOKUP


def resolve_waypoints(wps, warn_prefix=""):
    out = []
    for w in wps:
        if len(w) == 3:
            kind, nm = w[2].split(":", 1)
            hit = lookup().peak(nm, w[0], w[1]) if kind == "peak" else lookup().lake(nm, w[0], w[1])
            if hit:
                out.append((hit[1], hit[2]))
                continue
            print(f"    ?? {warn_prefix}: {w[2]} not found near ({w[0]}, {w[1]}); using given coords")
        out.append((w[0], w[1]))
    return out


def route_trail(waypoints, name_re=None, margin=None):
    xs = [p[0] for p in waypoints]
    ys = [p[1] for p in waypoints]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    m = margin if margin is not None else max(0.03, span * 0.25)
    net = TrailNetwork((min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m), name_re)
    res = net.route(waypoints)
    if res[0] is None:
        return None, res[1], 0.0
    return res


def route_long(guide, name_re, chunk=30, margin=0.03):
    """Route a long trail chunk-by-chunk along dense guide points."""
    parts = []
    for i in range(0, len(guide) - 1, chunk):
        ln, _, _ = route_trail(guide[i:i + chunk + 1], name_re=name_re, margin=margin)
        if ln is None:
            raise RuntimeError(f"routing failed for guide chunk starting at {guide[i]}")
        parts.append(ln)
    merged = linemerge(MultiLineString(parts))
    return merged


def elevation_gain_ft(coords3d, smooth=5):
    els = [c[2] for c in coords3d]
    if len(els) < 3:
        return 0
    half = smooth // 2
    sm = [sum(els[max(0, i - half):i + half + 1]) / len(els[max(0, i - half):i + half + 1]) for i in range(len(els))]
    gain = sum(max(0.0, b - a) for a, b in zip(sm, sm[1:]))
    return int(round(gain * 3.28084, -2))


def _nearest_index(coords, lon, lat):
    return min(range(len(coords)), key=lambda i: (coords[i][0] - lon) ** 2 + (coords[i][1] - lat) ** 2)


def _fmt_miles(m):
    return f"{m:,.0f}" if m >= 100 else f"{m:.1f}"


def build_pct_sections():
    from trail_catalog import PCT_COLOR
    pct = _download_cached(HALFMILE_PCT_URL, "halfmile_pct.geojson")
    coords = []
    for f in pct["features"][:4]:  # Desert, Sierra Nevada, Truckee-Chester, Northern California
        c = f["geometry"]["coordinates"]
        coords += c if not coords else c[1:]
    coords = [c for c in coords if c[1] <= 42.0]
    coords = coords[_nearest_index(coords, -118.0330, 35.6626):]  # start at Walker Pass (Hwy 178)
    cuts = [
        ("PCT: Southern Sierra (Walker Pass to Kennedy Meadows)", (-118.13412, 36.02372),
         "South Sierra Wilderness / Sequoia NF",
         "Desert-to-mountain transition over Walker Pass and the Scodie and Owens Peak ranges to the Kennedy Meadows 'gateway to the Sierra'.",
         "Walker Pass / Kennedy Meadows"),
        ("PCT: High Sierra (Kennedy Meadows to Tuolumne Meadows)", (-119.3428, 37.8767),
         "Sequoia-Kings Canyon, John Muir & Ansel Adams Wildernesses",
         "The crown of the PCT: Forester Pass (13,153 ft, highest point on the trail), Glen, Pinchot, Mather, Muir and Selden Passes, shared with the JMT for ~170 miles.",
         "Kennedy Meadows / Horseshoe Meadow / Onion Valley / Reds Meadow / Tuolumne Meadows"),
        ("PCT: Northern Sierra (Tuolumne Meadows to Donner Pass)", (-120.33595, 39.34243),
         "Yosemite, Emigrant, Carson-Iceberg, Mokelumne, Desolation & Granite Chief Wildernesses",
         "Northern Yosemite's deep canyons, the volcanic Sonora Pass crest, Carson Pass wildflowers, and Desolation's granite lakes to Donner Summit.",
         "Tuolumne Meadows / Sonora Pass / Ebbetts Pass / Carson Pass / Echo Summit / Donner Summit"),
        ("PCT: Feather River Country (Donner Pass to Chester)", (-121.3389, 40.26141),
         "Tahoe & Plumas National Forests / Bucks Lake Wilderness",
         "Sierra Buttes, the Lakes Basin, and the deep Middle and North Fork Feather River canyons down to Belden.",
         "Sierra City / Bucks Lake / Belden / Chester"),
        ("PCT: Northern California (Chester to Oregon Border)", None,
         "Lassen Volcanic NP / Castle Crags / Trinity Alps / Marble Mountains",
         "Lassen's volcanic backcountry, Hat Creek Rim, Burney Falls, Castle Crags, and the Klamath Mountains to Seiad Valley and the Siskiyou crest.",
         "Drakesbad / Old Station / Burney Falls / Castle Crags / Etna Summit / Seiad Valley"),
    ]
    feats = []
    start = 0
    for name, cut, park, desc, camp in cuts:
        end = len(coords) - 1 if cut is None else _nearest_index(coords, *cut)
        seg = coords[start:end + 1]
        start = end
        line = LineString([(c[0], c[1]) for c in seg])
        miles = length_miles(line)
        gain = elevation_gain_ft(seg)
        geom = line.simplify(0.00008, preserve_topology=False)
        feats.append({"type": "Feature", "properties": {
            "name": name, "park_name": park, "category": "National Scenic Trail", "trail_type": "pct",
            "difficulty": "Epic / Multi-day (PCT long-distance permit)",
            "distance_miles": f"{_fmt_miles(miles)} mi section", "elevation_gain_ft": f"≈{gain:,} ft cumulative",
            "trailhead_campground": camp, "color": PCT_COLOR, "region": "Pacific Crest Trail",
            "description": desc + " Track: Halfmile PCT survey."}, "geometry": to_geojson_geom(geom)})
        print(f"    {name}: {miles:.0f} mi, +{gain:,} ft, {len(geom.coords)} pts")
    return feats


def build_trails():
    from trail_catalog import TRAILS, ORANGE, JMT_COLOR, TRT_COLOR, TAHOE_RIM_TRAIL_WAYPOINTS
    feats = build_pct_sections()

    # John Muir Trail: routed along OSM, guided by a dense JMT trace (Happy Isles -> Whitney).
    g = _download_cached(JMT_GUIDE_URL, "jmt_guide.geojson")
    gc = g["geometry"]["coordinates"] if "geometry" in g else g["features"][0]["geometry"]["coordinates"]
    jmt = route_long([tuple(c[:2]) for c in gc[::-1]], r"John Muir|Pacific Crest")
    miles = length_miles(jmt)
    feats.append({"type": "Feature", "properties": {
        "name": "John Muir Trail (JMT)", "park_name": "Yosemite / Ansel Adams / John Muir / Sequoia-Kings Canyon Wildernesses",
        "category": "National Recreation Trail", "trail_type": "jmt", "difficulty": "Epic / Multi-day (permit)",
        "distance_miles": f"{miles:.0f} mi (Happy Isles to Mt. Whitney)", "elevation_gain_ft": "≈47,000 ft cumulative",
        "trailhead_campground": "Happy Isles (Upper Pines) / Tuolumne Meadows / Reds Meadow / Whitney Portal",
        "color": JMT_COLOR, "region": "John Muir Trail",
        "description": "America's most famous trail: Yosemite Valley to the summit of Mount Whitney over Donohue, Silver, Selden, Muir, Mather, Pinchot, Glen and Forester Passes."},
        "geometry": to_geojson_geom(jmt.simplify(0.00006))})
    print(f"    John Muir Trail: {miles:.1f} mi")

    # Tahoe Rim Trail loop
    trt = route_long(TAHOE_RIM_TRAIL_WAYPOINTS, r"Tahoe Rim|Pacific Crest", chunk=1, margin=0.04)
    miles = length_miles(trt)
    feats.append({"type": "Feature", "properties": {
        "name": "Tahoe Rim Trail (TRT)", "park_name": "Lake Tahoe Basin MU / Desolation / Mount Rose / Granite Chief Wildernesses",
        "category": "Long-Distance Loop Trail", "trail_type": "trt", "difficulty": "Epic / Multi-day",
        "distance_miles": f"{miles:.0f} mi loop", "elevation_gain_ft": "≈24,000 ft cumulative",
        "trailhead_campground": "Tahoe City / Brockway / Tahoe Meadows / Spooner / Kingsbury / Big Meadow / Echo Summit / Barker Pass",
        "color": TRT_COLOR, "region": "Lake Tahoe",
        "description": "Full circumnavigation of Lake Tahoe along the ridgetops of two states, sharing 50 miles with the PCT through Desolation and Granite Chief."},
        "geometry": to_geojson_geom(trt.simplify(0.00006))})
    print(f"    Tahoe Rim Trail: {miles:.1f} mi")

    problems = []
    for t in TRAILS:
        wps = resolve_waypoints(t["wp"], t["name"])
        ln, snaps, frac = route_trail(wps, name_re=t.get("re"))
        if ln is None:
            problems.append(f"{t['name']}: NO ROUTE")
            continue
        L = length_miles(ln)
        closed = t["wp"][0][:2] == t["wp"][-1][:2]
        kind = t["kind"]
        if closed and kind == "out-and-back":
            dist = f"{L:.1f} mi round-trip"
        elif kind == "out-and-back":
            dist = f"{2 * L:.1f} mi round-trip ({L:.1f} mi each way)"
        elif kind == "loop":
            dist = f"{L:.1f} mi loop"
        else:
            dist = f"{L:.1f} mi one-way"
        far = [round(s[1]) for s in snaps if s[1] > 400]
        flag = "  <-- CHECK" if (far or frac < 0.3) else ""
        print(f"    {t['name'][:48]:48} {L:6.1f} mi  named={frac:.2f}  far_snaps={far}{flag}")
        if flag:
            problems.append(f"{t['name']}: named={frac:.2f} far_snaps={far}")
        feats.append({"type": "Feature", "properties": {
            "name": t["name"], "park_name": t["park"], "category": "Hiking Trail", "trail_type": "hike",
            "difficulty": t["difficulty"], "distance_miles": dist, "elevation_gain_ft": t["gain"],
            "trailhead_campground": t["camp"], "color": ORANGE, "region": t["region"],
            "description": t["desc"]}, "geometry": to_geojson_geom(ln.simplify(0.00003))})

    with open(os.path.join(HERE, "prominent_trails.geojson"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    print(f"  prominent_trails.geojson: {len(feats)} trails, "
          f"{os.path.getsize(os.path.join(HERE, 'prominent_trails.geojson')) / 1e6:.2f} MB")
    if problems:
        print("  Trails to review:\n   - " + "\n   - ".join(problems))


# ---------------------------------------------------------------------------
# 3. Peaks & lakes (crosshair labels), rivers (lines), American River rafting runs
# ---------------------------------------------------------------------------
def build_landmarks():
    from landmark_catalog import PEAKS, LAKES
    feats = []
    for kind, specs in (("peak", PEAKS), ("lake", LAKES)):
        for disp, osm, lon, lat, elev, desc in specs:
            hit = lookup().peak(osm, lon, lat) if kind == "peak" else lookup().lake(osm, lon, lat, max_km=25)
            if hit:
                x, y = hit[1], hit[2]
                if kind == "peak" and hit[3]:
                    osm_ft = hit[3] * 3.28084
                    if abs(osm_ft - elev) > 150:
                        print(f"    note: {disp} OSM elevation {osm_ft:,.0f} ft vs catalog {elev:,} ft")
                moved = haversine_m(lon, lat, x, y)
                if moved > 800:
                    print(f"    {disp}: moved {moved / 1000:.1f} km to surveyed position")
            else:
                print(f"    ?? {disp}: no OSM {kind} named '{osm}' nearby; keeping catalog coords")
                x, y = lon, lat
            feats.append({"type": "Feature", "properties": {
                "name": disp, "type": kind, "elevation_ft": elev, "description": desc},
                "geometry": {"type": "Point", "coordinates": [round(x, 5), round(y, 5)]}})
    with open(os.path.join(HERE, "prominent_landmarks.geojson"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    print(f"  prominent_landmarks.geojson: {len(feats)} peaks & lakes")


def _river_lines(osm_names):
    tb = pq.read_table(os.path.join(CACHE, "water.parquet"), columns=["names", "subtype", "geometry"],
                       filters=ds.field(("names", "primary")).isin(osm_names) &
                       ds.field("subtype").isin(["river", "stream"]))
    lines = []
    for gb in tb.column("geometry").to_pylist():
        g = wkb.loads(gb)
        if g.geom_type == "LineString":
            lines.append(g)
        elif g.geom_type == "MultiLineString":
            lines.extend(g.geoms)
    return lines


def build_rivers():
    from landmark_catalog import RIVERS
    feats = []
    for disp, osm_names, desc in RIVERS:
        lines = _river_lines(osm_names)
        if not lines:
            print(f"    ?? {disp}: no river geometry")
            continue
        merged = linemerge(MultiLineString(lines))
        parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        parts = [p for p in parts if length_miles(p) > 0.3]
        geom = MultiLineString(parts).simplify(0.00025)
        miles = sum(length_miles(p) for p in parts)
        feats.append({"type": "Feature", "properties": {"name": disp, "type": "river", "description": desc,
                                                         "miles_mapped": round(miles)},
                      "geometry": to_geojson_geom(geom)})
        print(f"    {disp}: {len(parts)} reaches, {miles:,.0f} mi")
    with open(os.path.join(HERE, "rivers.geojson"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    print(f"  rivers.geojson: {len(feats)} rivers, {os.path.getsize(os.path.join(HERE, 'rivers.geojson')) / 1e6:.2f} MB")


def build_rafting():
    from landmark_catalog import RAFTING
    feats = []
    for name, river, put, take, klass, season, desc in RAFTING:
        merged = linemerge(MultiLineString(_river_lines([river])))
        parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        # choose the river reach that passes closest to both access points
        main = min(parts, key=lambda p: p.distance(Point(put[:2])) + p.distance(Point(take[:2])))
        a = main.project(Point(put[:2]))
        b = main.project(Point(take[:2]))
        pa, pb = main.interpolate(a), main.interpolate(b)
        for lbl, pt, snap in ((put[2], put, pa), (take[2], take, pb)):
            d = haversine_m(pt[0], pt[1], snap.x, snap.y)
            if d > 600:
                print(f"    note: {name}: {lbl} snapped {d:.0f} m onto the river")
        seg = substring(main, min(a, b), max(a, b))
        if b < a:
            seg = LineString(list(seg.coords)[::-1])
        miles = length_miles(seg)
        geom = seg.simplify(0.00008)
        props = {"name": name, "river": river, "class": klass, "season": season, "description": desc,
                 "put_in": put[2], "take_out": take[2], "length_miles": round(miles, 1),
                 "put_in_coords": [round(pa.x, 5), round(pa.y, 5)],
                 "take_out_coords": [round(pb.x, 5), round(pb.y, 5)]}
        feats.append({"type": "Feature", "properties": props, "geometry": to_geojson_geom(geom)})
        print(f"    {name}: {miles:.1f} mi ({klass})")
    with open(os.path.join(HERE, "rafting_sections.geojson"), "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    print(f"  rafting_sections.geojson: {len(feats)} runs")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
BUILDERS = {
    "boundaries": lambda: build_boundaries(),
    "trails": lambda: build_trails(),
    "landmarks": lambda: build_landmarks(),
    "rivers": lambda: build_rivers(),
    "rafting": lambda: build_rafting(),
}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--fetch" in args:
        fetch()
        args = [a for a in args if a != "--fetch"]
    for name in (args or list(BUILDERS)):
        print(f"\n== Building {name} ==")
        BUILDERS[name]()
