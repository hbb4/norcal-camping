import json

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

campgrounds = data["campgrounds"]
home = data["home_point"]

campgrounds_json_str = json.dumps(campgrounds)
home_json_str = json.dumps(home)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>California Campgrounds Explorer | Satellite & Roads</title>
  <!-- Tailwind CSS -->
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    #map {{
      width: 100%;
      height: 100%;
      min-height: 880px;
      border-radius: 16px;
      z-index: 1;
    }}
    .map-wrapper {{
      position: relative;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid #334155;
      box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.6);
    }}
    /* Clean simple radius text Southwest - no border, no background, no arrow */
    .simple-radius-label {{
      color: #94a3b8;
      font-size: 11px;
      font-weight: 500;
      white-space: nowrap;
      pointer-events: none;
      text-shadow: 0 1px 4px rgba(0,0,0,0.8);
    }}
    .leaflet-popup-content-wrapper {{
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 12px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
      padding: 4px;
    }}
    .leaflet-popup-tip {{
      background: #0f172a;
      border: 1px solid #334155;
    }}
    /* Custom scrollbars */
    ::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    ::-webkit-scrollbar-track {{
      background: rgba(15, 23, 42, 0.6);
    }}
    ::-webkit-scrollbar-thumb {{
      background: rgba(100, 116, 139, 0.5);
      border-radius: 3px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: rgba(148, 163, 184, 0.8);
    }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-4 md:p-8">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Header Section -->
    <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
      <div>
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            California Outdoor Operations
          </span>
          <span class="text-xs text-slate-300">
            Anchor: <strong class="text-white">Home</strong> (Nob Hill, SF)
          </span>
        </div>
        <h1 class="text-3xl font-extrabold tracking-tight text-white mt-1.5">
          California Campgrounds & Wilderness Explorer
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          High-resolution satellite imagery with federal & state highway networks, land cover, multi-field ratings, seasonal winter/summer intelligence, and booking portals across 69 California destinations.
        </p>
      </div>

      <!-- Quick Metrics -->
      <div class="flex items-center gap-3">
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-white" id="stat-total">69</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">Campgrounds</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-amber-400">8:00 AM</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">State Parks Drop</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-sky-400">7:00 AM</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">NPS / USFS Drop</span>
        </div>
      </div>
    </header>

    <!-- Controls & Filters Bar -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900/95 border border-slate-800 p-4 rounded-xl">
      <!-- Search -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Search Campground, Trail, or Mountain</label>
        <input 
          id="search-input" 
          type="text" 
          placeholder="e.g. Tahoe, Whitney, Desolation, Big Sur..." 
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
          oninput="applyFilters()"
        >
      </div>

      <!-- Region Filter -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Region Focus</label>
        <select 
          id="region-filter" 
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          onchange="applyFilters()"
        >
          <option value="ALL">All Regions (California & Sierra Overview)</option>
          <option value="San Francisco">San Francisco (City Limits)</option>
          <option value="Marin / SF Bay">Marin & Point Reyes</option>
          <option value="East Bay">East Bay Regional Parks</option>
          <option value="Half Moon Bay / Coast">Half Moon Bay & Coast</option>
          <option value="Santa Cruz Mountains">Santa Cruz Redwoods</option>
          <option value="South Bay / Diablo Range">South Bay & Diablo Range</option>
          <option value="Sonoma / Napa">Sonoma & Napa Valley</option>
          <option value="Monterey Bay & Salinas">Monterey Bay & Salinas</option>
          <option value="Monterey Bay & Big Sur">Monterey Bay & Big Sur</option>
          <option value="Lake Tahoe Basin">Lake Tahoe Basin (Winter & Summer)</option>
          <option value="Sierra Wilderness Areas">Sierra National Wilderness Areas</option>
          <option value="Eastern Sierra & Mono County">Eastern Sierra (Mono, June Lake, Mammoth)</option>
          <option value="Eastern Sierra & Inyo County">Eastern Sierra (Big Pine, Whitney, Alabama Hills)</option>
          <option value="Shasta / Trinity / Cascade">Shasta-Cascade & Trinity Alps</option>
        </select>
      </div>

      <!-- Reservation Rule Filter -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Reservation Rule</label>
        <select 
          id="rule-filter" 
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          onchange="applyFilters()"
        >
          <option value="ALL">All Reservation Types</option>
          <option value="Paid Reservation">Paid Reservation (ReserveCal / Rec.gov)</option>
          <option value="First-Come">First-Come First-Served (FCFS)</option>
          <option value="Dispersed">Dispersed / Free Wilderness ($0)</option>
        </select>
      </div>

      <!-- Agency Filter -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Managing Agency</label>
        <select 
          id="agency-filter" 
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          onchange="applyFilters()"
        >
          <option value="ALL">All Agencies</option>
          <option value="National Park Service">National Park Service (NPS)</option>
          <option value="California State Parks">California State Parks / NV Parks</option>
          <option value="US Forest Service">US Forest Service (USFS) / BLM</option>
          <option value="Regional">Regional & County Parks (EBRPD, San Mateo, Santa Clara)</option>
        </select>
      </div>
    </div>

    <!-- Map & Detail Panel Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
      
      <!-- Leaflet Map Container (8 cols on large screens, extended full height) -->
      <div class="lg:col-span-8 map-wrapper flex flex-col relative">
        
        <!-- Minimizable / Collapsible Map Legend (Positioned in UPPER RIGHT) -->
        <div id="collapsible-legend" class="absolute top-4 right-4 z-[1000] bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-xl p-3 text-xs shadow-2xl pointer-events-auto transition-all duration-200">
          <!-- Clickable Header that toggles collapse/expand -->
          <div id="legend-header" class="font-bold text-white text-[12px] flex items-center justify-between gap-3 cursor-pointer select-none hover:text-sky-300 transition" onclick="toggleLegend()" title="Click to collapse or expand legend">
            <span class="flex items-center gap-1.5">
              <span>🗺️</span> <span>Map Legend</span>
            </span>
            <span id="legend-toggle-icon" class="text-[11px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">Collapse ▲</span>
          </div>
          
          <!-- Collapsible Content -->
          <div id="legend-content" class="space-y-1.5 pt-2 border-t border-slate-700/80 mt-1.5">
            <div class="flex items-center gap-2">
              <span class="w-3.5 h-3.5 rounded-full bg-rose-500 inline-block ring-2 ring-rose-400/50"></span>
              <span class="text-slate-200 font-medium">Home (SF)</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-emerald-400 inline-block ring-1 ring-slate-900"></span>
              <span class="text-slate-300">California & Nevada State Parks</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-sky-400 inline-block ring-1 ring-slate-900"></span>
              <span class="text-slate-300">National Parks / NRA (NPS)</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-amber-400 inline-block ring-1 ring-slate-900"></span>
              <span class="text-slate-300">USFS / BLM / Wilderness ($0)</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-purple-400 inline-block ring-1 ring-slate-900"></span>
              <span class="text-slate-300">Regional & County Parks</span>
            </div>
            <div class="pt-1.5 text-[10px] text-slate-400 border-t border-slate-800">
              Dashed rings = 25, 50, 100, 200 mi from Home (labeled SW)
            </div>
          </div>
        </div>

        <!-- The Leaflet Map Element -->
        <div id="map" class="flex-1 w-full h-full min-h-[880px]"></div>
      </div>

      <!-- Detail Card & Inspector Panel (4 cols on large screens) -->
      <div class="lg:col-span-4 flex flex-col justify-between space-y-4">
        
        <!-- Selected Card Detail -->
        <div id="detail-card" class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div class="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <span id="card-region" class="px-2 py-0.5 text-[11px] font-semibold rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
                Region
              </span>
              <h2 id="card-title" class="text-xl font-bold text-white mt-1.5 leading-snug">
                Select a campground on map
              </h2>
              <p id="card-agency" class="text-xs text-slate-400 mt-0.5">Managing Agency</p>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-2.5 py-1 text-center">
                <span id="card-score" class="text-lg font-black text-emerald-400">9.2</span>
                <span class="block text-[9px] uppercase tracking-wider text-slate-400">Composite / 10</span>
              </div>
            </div>
          </div>

          <!-- Multi-Dimensional Specific Ratings Grid -->
          <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2">
            <div class="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
              <span>Multi-Field Assessment</span>
              <span id="card-comp-badge" class="px-2 py-0.5 text-[10px] rounded font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Competition: High
              </span>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center text-xs">
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]">🥾 Hiking</span>
                <strong id="card-rating-hiking" class="text-sky-400 text-sm">9.5 / 10</strong>
              </div>
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]">🌅 Views</span>
                <strong id="card-rating-views" class="text-amber-400 text-sm">9.0 / 10</strong>
              </div>
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]">⛺ Comfort</span>
                <strong id="card-rating-comfort" class="text-emerald-400 text-sm">8.0 / 10</strong>
              </div>
            </div>
          </div>

          <!-- Quick Stats Grid -->
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-800/70 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase font-semibold">Drive from Home</span>
              <span id="card-drive" class="font-bold text-white text-sm">45 mins (~21 mi)</span>
            </div>
            <div class="bg-slate-800/70 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase font-semibold">Capacity</span>
              <span id="card-capacity" class="font-bold text-white text-sm">31 campsites</span>
            </div>
          </div>

          <!-- Seasonal Profile & Winter Intelligence Callout -->
          <div class="bg-sky-950/25 border border-sky-700/40 rounded-xl p-3 space-y-2 text-xs">
            <div class="flex items-center justify-between">
              <span class="font-bold text-sky-300 uppercase tracking-wider flex items-center gap-1.5">
                <span>❄️</span> Winter & Seasonal Intelligence
              </span>
            </div>
            <div class="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span class="text-slate-400 block font-semibold">☀️ Peak Season:</span>
                <span id="card-peak-season" class="text-slate-200 font-medium">Jul – Aug</span>
              </div>
              <div>
                <span class="text-slate-400 block font-semibold">🍂 Light / Off-Season:</span>
                <span id="card-light-season" class="text-slate-200 font-medium">Nov – Apr</span>
              </div>
            </div>
            <div class="pt-1.5 border-t border-sky-900/50">
              <span class="text-slate-400 block font-semibold text-[10.5px]">Winter Access & Snow Profile:</span>
              <p id="card-winter-profile" class="text-slate-300 text-[11px] leading-relaxed mt-0.5">
                Seasonal road and snow profile.
              </p>
            </div>
          </div>

          <!-- Reservation Intelligence Callout -->
          <div class="bg-amber-950/30 border border-amber-600/40 rounded-xl p-3.5 space-y-1.5">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-amber-400"></span>
              <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider" id="card-rule-title">Reservation Rule & Window</h3>
            </div>
            <p class="text-xs text-amber-100/90 leading-relaxed" id="card-window">
              Select a campground to view exact release times and rules.
            </p>
            <div class="pt-1.5 flex items-center justify-between text-[11px] text-amber-200/80 border-t border-amber-900/50">
              <span>Nightly Fee:</span>
              <strong id="card-fee" class="text-white text-xs">$35 / night</strong>
            </div>
          </div>

          <!-- Hikes & Natural Attractions -->
          <div class="space-y-1.5">
            <h4 class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <span>🥾</span> Nearby Hikes & Natural Attractions
            </h4>
            <p id="card-hikes" class="text-xs text-slate-300 bg-slate-800/60 p-2.5 rounded-lg border border-slate-800 leading-relaxed">
              Nearby hiking trails and natural landmarks.
            </p>
          </div>

          <!-- Direct Action Buttons -->
          <div class="pt-3 border-t border-slate-800 space-y-2">
            <div class="flex items-center gap-2">
              <a id="card-reserve-btn" href="#" target="_blank" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-center py-2.5 px-3 rounded-lg text-xs font-bold shadow-md transition flex items-center justify-center gap-1.5">
                <span>🎫</span> Reserve Campsite Page ↗
              </a>
              <a id="card-inspect-btn" href="#" target="_blank" class="flex-1 bg-sky-600 hover:bg-sky-500 text-white text-center py-2.5 px-3 rounded-lg text-xs font-bold shadow-md transition flex items-center justify-center gap-1.5">
                <span>🏞️</span> Park Overview & Hikes ↗
              </a>
            </div>
            <a id="card-google-maps" href="#" target="_blank" class="block w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-center py-2 px-3 rounded-lg text-xs font-medium transition">
              🧭 Directions from Home (Google Maps) ↗
            </a>
          </div>

        </div>

        <!-- Strategy Quick Guide -->
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs space-y-2">
          <h3 class="font-bold text-white text-sm flex items-center gap-2">
            <span>⚡</span> Booking Window Cheat Sheet
          </h3>
          <ul class="space-y-1.5 text-slate-400 leading-normal">
            <li><strong class="text-emerald-400">ReserveCalifornia:</strong> 6 months rolling at <strong>8:00:00 AM PT</strong>. Steep Ravine, Big Sur, Sugar Pine Point open daily.</li>
            <li><strong class="text-sky-400">Recreation.gov:</strong> Most sites 6 months rolling at <strong>7:00:00 AM PT</strong>. Desolation Wilderness permits & Eastern Sierra campgrounds open 6 months rolling. Yosemite opens 15th of month.</li>
            <li><strong class="text-amber-400">First-Come, First-Served:</strong> Mt. Tamalpais (Pantoll/Bootjack) is open daily year-round; midweek is easy, but weekend campers should arrive by Friday 8:00 AM.</li>
          </ul>
        </div>

      </div>
    </div>

    <!-- Comprehensive Filterable Directory Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 class="text-xl font-bold text-white">Full Campground Directory & Multi-Field Ratings</h2>
          <p class="text-xs text-slate-400">Sorted from closest to furthest driving distance from Home (SF Nob Hill).</p>
        </div>
        <div class="text-xs text-slate-400">
          Showing <span id="table-count" class="font-bold text-white">69</span> campgrounds
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/40">
              <th class="py-3 px-3">Campground</th>
              <th class="py-3 px-3">Region</th>
              <th class="py-3 px-3">Agency</th>
              <th class="py-3 px-3">Drive from Home</th>
              <th class="py-3 px-3">Reservation Rule</th>
              <th class="py-3 px-3">Hiking / Views / Comfort</th>
              <th class="py-3 px-3">Competition</th>
              <th class="py-3 px-3">Peak Season</th>
              <th class="py-3 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody id="directory-tbody" class="divide-y divide-slate-800/60 text-slate-300">
            <!-- Dynamic rows populated via JS -->
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <!-- Client-Side Logic & Leaflet Map Initialization -->
  <script>
    const campgrounds = {campgrounds_json_str};
    const homePoint = {home_json_str};

    let selectedId = campgrounds[0].id;
    let filteredList = [...campgrounds];
    let markerLayerGroup = L.layerGroup();
    let ringsLayerGroup = L.layerGroup();
    let markerMap = {{}};
    let legendCollapsed = false;

    // Toggle Legend minimize/expand function
    function toggleLegend() {{
      const content = document.getElementById("legend-content");
      const icon = document.getElementById("legend-toggle-icon");
      legendCollapsed = !legendCollapsed;
      if (legendCollapsed) {{
        content.classList.add("hidden");
        icon.textContent = "Expand ▼";
      }} else {{
        content.classList.remove("hidden");
        icon.textContent = "Collapse ▲";
      }}
    }}

    // 1. Initialize Map centered on Northern & Central California
    const map = L.map('map', {{
      center: [38.2, -120.9],
      zoom: 7,
      zoomControl: true,
      minZoom: 6,
      maxZoom: 17
    }});

    // 2. Basemap Layers
    const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
      maxZoom: 19
    }});
    const esriRoads = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Roads &copy; Esri',
      maxZoom: 19
    }});
    const esriLabels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Labels &copy; Esri',
      maxZoom: 19
    }});
    const satelliteHybrid = L.layerGroup([esriSatellite, esriRoads, esriLabels]);

    const usgsTopo = L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'USGS National Map &mdash; Topo & Land Cover',
      maxZoom: 16
    }});

    const osmOutdoors = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }});

    satelliteHybrid.addTo(map);

    const baseLayers = {{
      "🛰️ Satellite + Major Roads (Default)": satelliteHybrid,
      "🌲 USGS Topo & Land Cover": usgsTopo,
      "🗺️ Street & Outdoors (OSM)": osmOutdoors
    }};
    L.control.layers(baseLayers, null, {{ position: 'topleft' }}).addTo(map);

    markerLayerGroup.addTo(map);
    ringsLayerGroup.addTo(map);

    function getAgencyColor(agency) {{
      if (agency.includes("National Park") || agency.includes("NPS")) return "#38bdf8"; // sky blue
      if (agency.includes("State Park") || agency.includes("State Rec") || agency.includes("Nevada State")) return "#34d399"; // emerald green
      if (agency.includes("Forest") || agency.includes("BLM")) return "#fbbf24"; // amber
      return "#c084fc"; // purple for regional/county
    }}

    // Draw Distance Rings with SIMPLE clean labels Southwest over ocean
    function drawDistanceRings() {{
      ringsLayerGroup.clearLayers();

      const rings = [
        {{ label: "25 mi", meters: 25 * 1609.34, labelLat: 37.536, labelLng: -122.738 }},
        {{ label: "50 mi", meters: 50 * 1609.34, labelLat: 37.280, labelLng: -123.062 }},
        {{ label: "100 mi", meters: 100 * 1609.34, labelLat: 36.768, labelLng: -123.712 }},
        {{ label: "200 mi", meters: 200 * 1609.34, labelLat: 35.745, labelLng: -125.011 }}
      ];

      rings.forEach(r => {{
        L.circle([homePoint.lat, homePoint.lng], {{
          radius: r.meters,
          color: '#94a3b8',
          weight: 1.1,
          dashArray: '5, 6',
          fill: false,
          opacity: 0.45
        }}).addTo(ringsLayerGroup);

        const labelIcon = L.divIcon({{
          className: 'simple-radius-label',
          html: r.label,
          iconSize: [45, 16],
          iconAnchor: [22, 8]
        }});

        L.marker([r.labelLat, r.labelLng], {{ icon: labelIcon, interactive: false }}).addTo(ringsLayerGroup);
      }});

      // Home Marker
      const homeMarker = L.circleMarker([homePoint.lat, homePoint.lng], {{
        radius: 7.5,
        fillColor: '#f43f5e',
        color: '#ffffff',
        weight: 2,
        fillOpacity: 1
      }}).addTo(ringsLayerGroup);

      homeMarker.bindTooltip("<strong>Home</strong><br><span style='font-size:11px;color:#cbd5e1'>Nob Hill, San Francisco</span>", {{
        permanent: false,
        direction: 'top',
        className: 'leaflet-popup-content-wrapper'
      }});

      L.circleMarker([homePoint.lat, homePoint.lng], {{
        radius: 13,
        fillColor: '#f43f5e',
        color: '#f43f5e',
        weight: 1.5,
        fillOpacity: 0.15,
        opacity: 0.6
      }}).addTo(ringsLayerGroup);
    }}

    drawDistanceRings();

    // Render Campground Markers
    function renderMarkers() {{
      markerLayerGroup.clearLayers();
      markerMap = {{}};

      filteredList.forEach(cg => {{
        const color = getAgencyColor(cg.agency);
        const isSelected = cg.id === selectedId;

        const marker = L.circleMarker([cg.lat, cg.lng], {{
          radius: isSelected ? 7.5 : 5.5,
          fillColor: color,
          color: isSelected ? '#ffffff' : '#0f172a',
          weight: isSelected ? 2.5 : 1.2,
          fillOpacity: 0.95
        }});

        marker.bindTooltip(`<strong>${{cg.name}}</strong><br><span style='font-size:11px;color:#94a3b8'>${{cg.drive_time_from_home}} (${{cg.distance_road_miles}} mi) • ${{cg.reservation_type}}</span>`, {{
          direction: 'top',
          offset: [0, -6]
        }});

        const popupContent = `
          <div style="font-size:12px; min-width:210px;">
            <div style="font-weight:bold; font-size:13px; color:#ffffff; margin-bottom:2px;">${{cg.name}}</div>
            <div style="color:#94a3b8; font-size:11px; margin-bottom:6px;">${{cg.agency}} • ${{cg.region}}</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <span style="color:#cbd5e1">Drive from Home:</span>
              <strong style="color:#38bdf8">${{cg.drive_time_from_home}}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
              <span style="color:#cbd5e1">Reservation:</span>
              <span style="color:#34d399; font-weight:600">${{cg.reservation_type}}</span>
            </div>
            <div style="margin-top:8px; display:flex; gap:6px;">
              <a href="${{cg.direct_booking_url}}" target="_blank" style="background:#059669; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold; text-decoration:none; font-size:10.5px; flex:1; text-align:center;">Reserve ↗</a>
              <a href="${{cg.overview_url}}" target="_blank" style="background:#0284c7; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold; text-decoration:none; font-size:10.5px; flex:1; text-align:center;">Overview ↗</a>
            </div>
          </div>
        `;
        marker.bindPopup(popupContent);

        marker.on('click', () => {{
          selectCampground(cg.id, false);
        }});

        marker.addTo(markerLayerGroup);
        markerMap[cg.id] = marker;
      }});
    }}

    function selectCampground(id, panTo = true) {{
      selectedId = id;
      const cg = campgrounds.find(c => c.id === id);
      if (!cg) return;

      document.getElementById("card-region").textContent = cg.region;
      document.getElementById("card-title").textContent = cg.name;
      document.getElementById("card-agency").textContent = cg.agency;
      document.getElementById("card-score").textContent = cg.composite_score_out_of_10.toFixed(1);
      
      // Multi-dimensional ratings
      document.getElementById("card-rating-hiking").textContent = `${{cg.rating_hiking.toFixed(1)}} / 10`;
      document.getElementById("card-rating-views").textContent = `${{cg.rating_views.toFixed(1)}} / 10`;
      document.getElementById("card-rating-comfort").textContent = `${{cg.rating_comfort.toFixed(1)}} / 10`;
      document.getElementById("card-comp-badge").textContent = `Competition: ${{cg.competition_badge || (cg.rating_competition + '/10')}}`;

      // Seasonal & Winter profile
      document.getElementById("card-peak-season").textContent = cg.peak_season || "Jun – Sep";
      document.getElementById("card-light-season").textContent = cg.light_season || "Nov – Apr";
      document.getElementById("card-winter-profile").textContent = cg.winter_profile || "Open with winter weather variations.";

      document.getElementById("card-drive").textContent = `${{cg.drive_time_from_home}} (~${{cg.distance_road_miles}} mi)`;
      document.getElementById("card-capacity").textContent = `${{cg.num_sites}} sites (${{cg.site_types}})`;
      document.getElementById("card-rule-title").textContent = cg.reservation_type;
      document.getElementById("card-window").textContent = cg.reservation_window;
      document.getElementById("card-fee").textContent = cg.nightly_fee;
      document.getElementById("card-hikes").textContent = cg.nearby_hikes_attractions;

      document.getElementById("card-reserve-btn").href = cg.direct_booking_url;
      document.getElementById("card-inspect-btn").href = cg.overview_url;
      
      const mapsQuery = encodeURIComponent(`${{cg.name}}, California`);
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/dir/Grace+Cathedral,+1100+California+St,+San+Francisco,+CA+94108/${{mapsQuery}}`;

      const m = markerMap[id];
      if (m) {{
        if (panTo) {{
          map.panTo([cg.lat, cg.lng], {{ animate: true, duration: 0.5 }});
        }}
        m.openPopup();
      }}

      Object.keys(markerMap).forEach(key => {{
        const isCurrent = key === id;
        const currentCg = campgrounds.find(c => c.id === key);
        if (currentCg && markerMap[key]) {{
          markerMap[key].setStyle({{
            radius: isCurrent ? 7.5 : 5.5,
            color: isCurrent ? '#ffffff' : '#0f172a',
            weight: isCurrent ? 2.5 : 1.2
          }});
        }}
      }});
    }}

    function renderTable() {{
      const tbody = document.getElementById("directory-tbody");
      tbody.innerHTML = "";
      document.getElementById("table-count").textContent = filteredList.length;

      filteredList.forEach(cg => {{
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-800/40 transition cursor-pointer";

        tr.innerHTML = `
          <td class="py-3 px-3 font-semibold text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full inline-block flex-shrink-0" style="background-color: ${{getAgencyColor(cg.agency)}}"></span>
            <span>${{cg.name}}</span>
          </td>
          <td class="py-3 px-3 text-slate-400 whitespace-nowrap">${{cg.region}}</td>
          <td class="py-3 px-3 text-slate-400 whitespace-nowrap">${{cg.agency}}</td>
          <td class="py-3 px-3 font-medium text-slate-200 whitespace-nowrap">
            ${{cg.drive_time_from_home}} <span class="text-slate-500">(${{cg.distance_road_miles}} mi)</span>
          </td>
          <td class="py-3 px-3">
            <span class="px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap ${{
              cg.reservation_type.includes('Paid') ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20' :
              cg.reservation_type.includes('First-Come') ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
              'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            }}">
              ${{cg.reservation_type}}
            </span>
          </td>
          <td class="py-3 px-3 text-slate-300 whitespace-nowrap">
            <span class="text-sky-400 font-semibold" title="Hiking">${{cg.rating_hiking.toFixed(1)}}</span> / 
            <span class="text-amber-400 font-semibold" title="Views">${{cg.rating_views.toFixed(1)}}</span> / 
            <span class="text-emerald-400 font-semibold" title="Comfort">${{cg.rating_comfort.toFixed(1)}}</span>
          </td>
          <td class="py-3 px-3 whitespace-nowrap">
            <span class="px-2 py-0.5 rounded text-[10.5px] font-medium ${{
              cg.rating_competition >= 9 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30' :
              cg.rating_competition >= 7 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
              'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
            }}">
              ${{cg.competition_badge || (cg.rating_competition + '/10')}}
            </span>
          </td>
          <td class="py-3 px-3 text-slate-400 whitespace-nowrap">${{cg.peak_season || "Summer"}}</td>
          <td class="py-3 px-3 text-right whitespace-nowrap space-x-1.5">
            <a href="${{cg.direct_booking_url}}" target="_blank" onclick="event.stopPropagation();" class="bg-emerald-700 hover:bg-emerald-600 text-white px-2 py-1 rounded text-[11px] font-semibold transition" title="Go directly to reservation booking engine">
              Reserve ↗
            </a>
            <a href="${{cg.overview_url}}" target="_blank" onclick="event.stopPropagation();" class="bg-sky-700 hover:bg-sky-600 text-white px-2 py-1 rounded text-[11px] font-semibold transition" title="View Park Overview & Hikes">
              Inspect ↗
            </a>
          </td>
        `;

        tr.onclick = () => {{
          selectCampground(cg.id, true);
          window.scrollTo({{ top: 120, behavior: "smooth" }});
        }};

        tbody.appendChild(tr);
      }});
    }}

    function applyFilters() {{
      const query = document.getElementById("search-input").value.toLowerCase().trim();
      const region = document.getElementById("region-filter").value;
      const rule = document.getElementById("rule-filter").value;
      const agency = document.getElementById("agency-filter").value;

      filteredList = campgrounds.filter(cg => {{
        const matchesQuery = !query || 
          cg.name.toLowerCase().includes(query) || 
          cg.nearby_hikes_attractions.toLowerCase().includes(query) ||
          cg.region.toLowerCase().includes(query) ||
          (cg.description && cg.description.toLowerCase().includes(query)) ||
          (cg.winter_profile && cg.winter_profile.toLowerCase().includes(query));

        const matchesRegion = (region === "ALL") || (cg.region === region);
        
        let matchesRule = true;
        if (rule === "Paid Reservation") matchesRule = cg.reservation_type.includes("Paid");
        if (rule === "First-Come") matchesRule = cg.reservation_type.includes("First-Come");
        if (rule === "Dispersed") matchesRule = cg.reservation_type.includes("Dispersed") || cg.nightly_fee.includes("$0") || cg.nightly_fee.toLowerCase().includes("free");

        let matchesAgency = true;
        if (agency === "National Park Service") matchesAgency = cg.agency.includes("National Park") || cg.agency.includes("NPS");
        if (agency === "California State Parks") matchesAgency = cg.agency.includes("California State Parks") || cg.agency.includes("State Rec") || cg.agency.includes("Nevada State");
        if (agency === "US Forest Service") matchesAgency = cg.agency.includes("Forest") || cg.agency.includes("BLM");
        if (agency === "Regional") matchesAgency = cg.agency.includes("Regional") || cg.agency.includes("County") || cg.agency.includes("Reclamation") || cg.agency.includes("Tribe");

        return matchesQuery && matchesRegion && matchesRule && matchesAgency;
      }});

      renderMarkers();
      renderTable();

      if (filteredList.length > 0) {{
        const bounds = L.latLngBounds(filteredList.map(c => [c.lat, c.lng]));
        bounds.extend([homePoint.lat, homePoint.lng]);
        map.fitBounds(bounds, {{ padding: [40, 40], maxZoom: 12 }});
      }}
    }}

    renderMarkers();
    renderTable();
    selectCampground(selectedId, false);
  </script>
</body>
</html>
"""

with open("campground_map_dashboard.html", "w") as f:
    f.write(html_content)

artifact_path = "/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/campground_explorer.html"
with open(artifact_path, "w") as f:
    f.write(html_content)

print("Updated campground_map_dashboard.html with collapsible legend, multi-field ratings, and 69 campgrounds!")
