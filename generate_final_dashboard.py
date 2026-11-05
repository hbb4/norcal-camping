# generate_final_dashboard.py
import json

with open("campgrounds_data.json", "r") as f:
    cg_data = json.load(f)

with open("park_boundaries.geojson", "r") as f:
    boundaries_data = json.load(f)

with open("prominent_trails.geojson", "r") as f:
    trails_data = json.load(f)

with open("prominent_landmarks.geojson", "r") as f:
    landmarks_data = json.load(f)

with open("rivers.geojson", "r") as f:
    rivers_data = json.load(f)

with open("rafting_sections.geojson", "r") as f:
    rafting_data = json.load(f)

# Landmarks whose labels stay visible even at the widest zoom levels
MAJOR_LANDMARKS = {
    "Mount Whitney", "Mount Shasta", "Lassen Peak", "Half Dome", "Mount Diablo", "Mount Tamalpais (East Peak)",
    "Mount Tallac", "Mount Rose", "Thompson Peak", "Mount Lyell", "North Palisade", "Cone Peak", "Mount Saint Helena",
    "Lake Tahoe", "Mono Lake", "Shasta Lake", "Trinity Lake", "Clear Lake", "Lake Berryessa", "Lake Almanor",
    "Lake Oroville", "Folsom Lake", "Whiskeytown Lake",
}
for _f in landmarks_data["features"]:
    _f["properties"]["major"] = _f["properties"]["name"] in MAJOR_LANDMARKS

campgrounds = cg_data["campgrounds"]
home = cg_data["home_point"]

campgrounds_json_str = json.dumps(campgrounds)
boundaries_json_str = json.dumps(boundaries_data)
trails_json_str = json.dumps(trails_data)
landmarks_json_str = json.dumps(landmarks_data)
rivers_json_str = json.dumps(rivers_data, separators=(",", ":"))
rafting_json_str = json.dumps(rafting_data)

n_parks = sum(1 for f in boundaries_data["features"] if f["properties"].get("layer") != "forests")
n_forests = sum(1 for f in boundaries_data["features"] if f["properties"].get("layer") == "forests")
n_wilderness = sum(1 for f in boundaries_data["features"] if "Wilderness" in f["properties"]["category"])
n_trails = len(trails_data["features"])
n_landmarks = len(landmarks_data["features"])
n_rivers = len(rivers_data["features"])
home_json_str = json.dumps(home)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>California Campgrounds Explorer | High-Resolution Parks, Trails & Peaks</title>
  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    #map {{
      width: 100%;
      height: 100%;
      min-height: 890px;
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
      text-shadow: 0 1px 4px rgba(0,0,0,0.85);
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
    .boundary-tooltip {{
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #475569;
      color: #f8fafc;
      border-radius: 8px;
      padding: 5px 9px;
      font-size: 11.5px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.5);
    }}
    .trail-tooltip {{
      background: rgba(15, 23, 42, 0.95);
      border: 1.5px solid #f97316;
      color: #f8fafc;
      border-radius: 8px;
      padding: 5px 9px;
      font-size: 11.5px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.6);
    }}
    .landmark-tooltip {{
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #38bdf8;
      color: #f8fafc;
      border-radius: 8px;
      padding: 5px 9px;
      font-size: 11.5px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.6);
    }}
    /* Peak & lake crosshairs: the crosshair center sits exactly on the coordinate; the label is pinned to its right */
    .landmark-xhair {{
      pointer-events: auto;
      cursor: pointer;
    }}
    .landmark-xhair svg {{
      position: absolute;
      left: 0;
      top: 0;
      overflow: visible;
    }}
    .landmark-xhair .lm-label {{
      position: absolute;
      left: 19px;
      top: 0;
      line-height: 18px;
      white-space: nowrap;
      font-size: 10.5px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: 0.01em;
      text-shadow: 0 0 3px #020617, 0 0 2px #020617, 0 1px 4px #020617, 0 0 1px #020617;
    }}
    .landmark-xhair .lm-elev {{
      font-weight: 600;
      font-size: 9.5px;
      margin-left: 4px;
    }}
    .lm-compact .landmark-xhair .lm-label.minor {{
      display: none;
    }}
    /* Let clicks on empty SVG overlay space fall through to the canvas-rendered park boundaries
       (trail / river / rafting paths keep their own pointer events). */
    .leaflet-pane > svg {{
      pointer-events: none;
    }}
    /* River names drawn along each river's path */
    .river-label {{
      font-size: 11px;
      font-weight: 700;
      font-style: italic;
      fill: #bfdbfe;
      stroke: #0b1a33;
      stroke-width: 3px;
      paint-order: stroke;
      letter-spacing: 0.06em;
      pointer-events: none;
    }}
    .raft-label {{
      background: rgba(15, 23, 42, 0.92);
      border: 1.5px solid #2dd4bf;
      color: #f8fafc;
      border-radius: 8px;
      padding: 5px 9px;
      font-size: 11.5px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.6);
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
          Campgrounds, Parks, Trails & Wilderness Explorer
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          Featuring <strong class="text-emerald-400">{n_parks} park & wilderness boundaries plus {n_forests} national forests</strong>, <strong class="text-amber-400">{n_trails} hiking trails incl. the PCT, JMT & Tahoe Rim Trail</strong>, <strong class="text-rose-400">peaks & lakes</strong>, {n_rivers} rivers, American River rafting runs, and <strong class="text-sky-400">{len(campgrounds)} individually listed campsites</strong>.
        </p>
      </div>

      <!-- Quick Metrics -->
      <div class="flex items-center gap-2.5 flex-wrap">
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-center">
          <span class="block text-xl font-bold text-white" id="stat-total">101</span>
          <span class="text-[10px] text-slate-400 uppercase tracking-wider">Campsites</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-center">
          <span class="block text-xl font-bold text-purple-400">{n_parks + n_forests}</span>
          <span class="text-[10px] text-slate-400 uppercase tracking-wider">Parks & Forests</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-center">
          <span class="block text-xl font-bold text-amber-400">{n_trails}</span>
          <span class="text-[10px] text-slate-400 uppercase tracking-wider">Trails</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-center">
          <span class="block text-xl font-bold text-rose-400">{n_landmarks}</span>
          <span class="text-[10px] text-slate-400 uppercase tracking-wider">Peaks & Lakes</span>
        </div>
      </div>
    </header>

    <!-- Controls & Filters Bar -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900/95 border border-slate-800 p-4 rounded-xl">
      <!-- Search -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Search Campsite, Park, Trail, or Peak</label>
        <input 
          id="search-input" 
          type="text" 
          placeholder="e.g. Mount Whitney, Dipsea, Steep Ravine, Desolation..." 
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
          <option value="East Bay">East Bay Regional Parks & Diablo</option>
          <option value="Half Moon Bay / Coast">Half Moon Bay & Coast</option>
          <option value="Santa Cruz Mountains">Santa Cruz Redwoods</option>
          <option value="South Bay / Diablo Range">South Bay & Henry Coe</option>
          <option value="Sonoma / Napa">Sonoma & Napa Valley</option>
          <option value="Sonoma / Coast">Sonoma Coast & Mendocino</option>
          <option value="Monterey Bay & Salinas">Monterey Bay & Salinas</option>
          <option value="Monterey Bay & Big Sur">Monterey Bay & Big Sur</option>
          <option value="Lake Tahoe Basin">Lake Tahoe Basin (Winter & Summer)</option>
          <option value="Sierra Wilderness Areas">Sierra National Wilderness Areas</option>
          <option value="Eastern Sierra & Mono County">Eastern Sierra (Mono, June Lake, Mammoth)</option>
          <option value="Eastern Sierra & Inyo County">Eastern Sierra (Palisades, Whitney, Alabama Hills)</option>
          <option value="Sierra Nevada">Sierra Nevada (Yosemite & Calaveras)</option>
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
        <div id="collapsible-legend" class="absolute top-4 right-4 z-[1000] bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-xl p-3 text-xs shadow-2xl pointer-events-auto transition-all duration-200 max-w-xs">
          <!-- Clickable Header that toggles collapse/expand -->
          <div id="legend-header" class="font-bold text-white text-[12px] flex items-center justify-between gap-3 cursor-pointer select-none hover:text-sky-300 transition" onclick="toggleLegend()" title="Click to collapse or expand legend">
            <span class="flex items-center gap-1.5">
              <span>🗺️</span> <span>Legend & Overlays</span>
            </span>
            <span id="legend-toggle-icon" class="text-[11px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">Collapse ▲</span>
          </div>
          
          <!-- Collapsible Content -->
          <div id="legend-content" class="space-y-2 pt-2 border-t border-slate-700/80 mt-1.5">
            <div class="text-[10.5px] uppercase tracking-wider text-slate-400 font-semibold">Map Features & Styling:</div>
            
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-3.5 h-3.5 rounded-full bg-rose-500 inline-block ring-2 ring-rose-400/50"></span>
                <span class="text-slate-200 font-medium">Home (SF)</span>
              </div>
            </div>

            <!-- Trails & Landmarks Styling -->
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1 bg-orange-500 inline-block rounded"></span>
                <span class="text-orange-300 font-medium">Hiking Trails</span>
              </div>
              <span class="text-[10px] text-amber-400 px-1 py-0.5 rounded bg-amber-950/60 border border-amber-600/40">Click trail to inspect</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1.5 inline-block rounded" style="background:#facc15; box-shadow:0 0 0 1px #0f172a;"></span>
                <span class="text-yellow-300 font-medium">Pacific Crest Trail</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono">Halfmile survey</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1.5 inline-block rounded" style="background:repeating-linear-gradient(90deg,#22d3ee 0 5px,transparent 5px 8px); box-shadow:0 0 0 1px #0f172a;"></span>
                <span class="text-cyan-300 font-medium">John Muir Trail</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono">Shares PCT tread</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1.5 inline-block rounded" style="background:#f8fafc; box-shadow:0 0 0 1px #0f172a;"></span>
                <span class="text-slate-100 font-medium">Tahoe Rim Trail</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono">165-mi loop</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="4.2" fill="none" stroke="#fb7185" stroke-width="1.8"/><path d="M9 0.5v5M9 12.5v5M0.5 9h5M12.5 9h5" stroke="#fb7185" stroke-width="1.8"/></svg>
                <span class="text-slate-300">Peaks</span>
              </div>
              <span class="text-[10px] text-rose-400 font-mono">Elevation (ft)</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="4.2" fill="none" stroke="#38bdf8" stroke-width="1.8"/><path d="M9 0.5v5M9 12.5v5M0.5 9h5M12.5 9h5" stroke="#38bdf8" stroke-width="1.8"/></svg>
                <span class="text-slate-300">Lakes</span>
              </div>
              <span class="text-[10px] text-sky-400 font-mono">Surface elev.</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1 inline-block rounded" style="background:#60a5fa;"></span>
                <span class="text-slate-300">Rivers (named along path)</span>
              </div>
              <span class="text-[10px] text-sky-400 font-mono">Zoom 10+</span>
            </div>

            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="w-4 h-1.5 inline-block rounded" style="background:#2dd4bf; box-shadow:0 0 0 1px #0f172a;"></span>
                <span class="text-teal-300 font-medium">American River Rafting</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono">Class II-IV</span>
            </div>

            <div class="border-t border-slate-800 pt-1.5 space-y-1.5">
              <div class="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Park Boundaries (Surveyed):</div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-emerald-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">State Parks</span>
                </div>
                <span class="text-[10px] text-emerald-400 px-1 py-0.5 rounded bg-emerald-950/60 border border-emerald-600/40 font-mono">Detailed</span>
              </div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-sky-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">National Parks / NRA</span>
                </div>
                <span class="text-[10px] text-sky-400 px-1 py-0.5 rounded bg-sky-950/60 border border-sky-600/40 font-mono">Detailed</span>
              </div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-purple-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">Wilderness Areas</span>
                </div>
                <span class="text-[10px] text-purple-400 px-1 py-0.5 rounded bg-purple-950/60 border border-purple-600/40 font-mono">[- -]</span>
              </div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-amber-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">National Monuments / NRA / BLM</span>
                </div>
                <span class="text-[10px] text-amber-400 px-1 py-0.5 rounded bg-amber-950/60 border border-amber-600/40 font-mono">Detailed</span>
              </div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-pink-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">Regional / County Parks</span>
                </div>
                <span class="text-[10px] text-pink-400 px-1 py-0.5 rounded bg-pink-950/60 border border-pink-600/40 font-mono">Detailed</span>
              </div>

              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-lime-400 inline-block ring-1 ring-slate-900"></span>
                  <span class="text-slate-300">National Forests (USFS)</span>
                </div>
                <span class="text-[10px] text-lime-400 px-1 py-0.5 rounded bg-lime-950/60 border border-lime-600/40 font-mono">[- -]</span>
              </div>
            </div>

            <div class="pt-1.5 text-[10px] text-slate-400 border-t border-slate-800 leading-tight">
              Hover boundary or trail for info; click to zoom or view in inspector card. Toggle layers in top-left control.
            </div>
          </div>
        </div>

        <!-- The Leaflet Map Element -->
        <div id="map" class="flex-1 w-full h-full min-h-[890px]"></div>
      </div>

      <!-- Detail Card & Inspector Panel (4 cols on large screens) -->
      <div class="lg:col-span-4 flex flex-col justify-between space-y-4">
        
        <!-- Selected Card Detail -->
        <div id="detail-card" class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div class="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <div class="flex items-center gap-2 flex-wrap">
                <span id="card-region" class="px-2 py-0.5 text-[11px] font-semibold rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
                  Region
                </span>
                <span id="card-park-badge" class="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Park Name
                </span>
              </div>
              <h2 id="card-title" class="text-xl font-bold text-white mt-1.5 leading-snug">
                Select a campsite, trail, or landmark
              </h2>
              <p id="card-agency" class="text-xs text-slate-400 mt-0.5">Managing Agency</p>
            </div>
            <div class="text-right flex-shrink-0" id="card-score-box">
              <div class="bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-2.5 py-1 text-center">
                <span id="card-score" class="text-lg font-black text-emerald-400">9.5</span>
                <span class="block text-[9px] uppercase tracking-wider text-slate-400" id="card-score-label">Composite / 10</span>
              </div>
            </div>
          </div>

          <!-- Multi-Dimensional Specific Ratings Grid (or Trail Stats Grid) -->
          <div id="card-metrics-grid" class="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2">
            <div class="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
              <span id="card-metrics-title">Multi-Field Assessment</span>
              <span id="card-comp-badge" class="px-2 py-0.5 text-[10px] rounded font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                Competition: Extreme (10/10)
              </span>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center text-xs">
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]" id="metric-label-1">🥾 Hiking</span>
                <strong id="card-rating-hiking" class="text-sky-400 text-sm">10.0 / 10</strong>
              </div>
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]" id="metric-label-2">🌅 Views</span>
                <strong id="card-rating-views" class="text-amber-400 text-sm">10.0 / 10</strong>
              </div>
              <div class="bg-slate-900/80 rounded-lg p-2 border border-slate-800">
                <span class="block text-slate-400 text-[10px]" id="metric-label-3">⛺ Comfort</span>
                <strong id="card-rating-comfort" class="text-emerald-400 text-sm">7.5 / 10</strong>
              </div>
            </div>
          </div>

          <!-- Quick Stats Grid -->
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-800/70 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase font-semibold" id="card-stat1-label">Drive from Home</span>
              <span id="card-drive" class="font-bold text-white text-sm">50 mins (~22 mi)</span>
            </div>
            <div class="bg-slate-800/70 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase font-semibold" id="card-stat2-label">Specific Capacity</span>
              <span id="card-capacity" class="font-bold text-white text-sm">10 rustic cabins</span>
            </div>
          </div>

          <!-- Seasonal Profile & Winter Intelligence Callout -->
          <div id="card-seasonal-box" class="bg-sky-950/25 border border-sky-700/40 rounded-xl p-3 space-y-2 text-xs">
            <div class="flex items-center justify-between">
              <span class="font-bold text-sky-300 uppercase tracking-wider flex items-center gap-1.5">
                <span>❄️</span> Winter & Seasonal Intelligence
              </span>
            </div>
            <div class="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span class="text-slate-400 block font-semibold">☀️ Peak Season:</span>
                <span id="card-peak-season" class="text-slate-200 font-medium">Year-Round</span>
              </div>
              <div>
                <span class="text-slate-400 block font-semibold">🍂 Light / Off-Season:</span>
                <span id="card-light-season" class="text-slate-200 font-medium">Winter storms</span>
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
          <div id="card-reservation-box" class="bg-amber-950/30 border border-amber-600/40 rounded-xl p-3.5 space-y-1.5">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-amber-400"></span>
              <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider" id="card-rule-title">Reservation Rule & Window</h3>
            </div>
            <p class="text-xs text-amber-100/90 leading-relaxed" id="card-window">
              Select a campsite to view exact release times and booking portals.
            </p>
            <div class="pt-1.5 flex items-center justify-between text-[11px] text-amber-200/80 border-t border-amber-900/50">
              <span id="card-fee-label">Nightly Fee:</span>
              <strong id="card-fee" class="text-white text-xs">$100 / night</strong>
            </div>
          </div>

          <!-- Hikes & Natural Attractions / Description -->
          <div class="space-y-1.5">
            <h4 class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <span id="card-hikes-icon">🥾</span> <span id="card-hikes-title">Direct Trailheads & Nearby Attractions</span>
            </h4>
            <p id="card-hikes" class="text-xs text-slate-300 bg-slate-800/60 p-2.5 rounded-lg border border-slate-800 leading-relaxed">
              Nearby hiking trails and natural landmarks.
            </p>
          </div>

          <!-- Direct Action Buttons -->
          <div class="pt-3 border-t border-slate-800 space-y-2">
            <div class="flex items-center gap-2">
              <a id="card-reserve-btn" href="#" target="_blank" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-center py-2.5 px-3 rounded-lg text-xs font-bold shadow-md transition flex items-center justify-center gap-1.5">
                <span>🎫</span> <span id="card-btn1-text">Reserve Campsite Page ↗</span>
              </a>
              <a id="card-inspect-btn" href="#" target="_blank" class="flex-1 bg-sky-600 hover:bg-sky-500 text-white text-center py-2.5 px-3 rounded-lg text-xs font-bold shadow-md transition flex items-center justify-center gap-1.5">
                <span>🏞️</span> <span id="card-btn2-text">Park Overview & Hikes ↗</span>
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
            <span>⚡</span> Navigation & Booking Shortcuts
          </h3>
          <ul class="space-y-1.5 text-slate-400 leading-normal">
            <li><strong class="text-amber-400">Hiking Trails Overlay:</strong> Click any orange trail line to inspect distance, elevation gain, difficulty, and connected campgrounds.</li>
            <li><strong class="text-rose-400">Peaks & Lakes:</strong> Click peak badges ⛰️ (e.g. Mount Whitney 14,505', Half Dome) or lakes 💧 for elevations and geography.</li>
            <li><strong class="text-emerald-400">ReserveCalifornia:</strong> 6 months rolling at <strong>8:00:00 AM PT</strong>.</li>
            <li><strong class="text-sky-400">Recreation.gov:</strong> 6 months rolling at <strong>7:00:00 AM PT</strong>. Yosemite opens on the 15th monthly.</li>
          </ul>
        </div>

      </div>
    </div>

    <!-- Comprehensive Filterable Directory Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 class="text-xl font-bold text-white">Full Individual Campsite Directory (101 Entries)</h2>
          <p class="text-xs text-slate-400">Every campground and campsite listed individually with exact capacity, ratings, and booking portals.</p>
        </div>
        <div class="text-xs text-slate-400">
          Showing <span id="table-count" class="font-bold text-white">101</span> campsites
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/40">
              <th class="py-3 px-3">Campsite Entry</th>
              <th class="py-3 px-3">Park / Area</th>
              <th class="py-3 px-3">Region</th>
              <th class="py-3 px-3">Drive from Home</th>
              <th class="py-3 px-3">Reservation Rule</th>
              <th class="py-3 px-3">Capacity</th>
              <th class="py-3 px-3">Hiking / Views / Comfort</th>
              <th class="py-3 px-3">Competition</th>
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
    const parkBoundaries = {boundaries_json_str};
    const prominentTrails = {trails_json_str};
    const prominentLandmarks = {landmarks_json_str};
    const riversData = {rivers_json_str};
    const raftingData = {rafting_json_str};
    const homePoint = {home_json_str};

    let selectedId = campgrounds[0].id;
    let filteredList = [...campgrounds];
    let markerLayerGroup = L.layerGroup();
    let ringsLayerGroup = L.layerGroup();
    let boundaryLayerGroup = L.layerGroup();
    let forestLayerGroup = L.layerGroup();
    let trailsLayerGroup = L.layerGroup();
    let landmarksLayerGroup = L.layerGroup();
    let riversLayerGroup = L.layerGroup();
    let riversToggle = L.layerGroup();   // layer-control proxy; real river layer only shows at zoom >= RIVER_MIN_ZOOM
    let raftingLayerGroup = L.layerGroup();
    const RIVER_MIN_ZOOM = 10;
    let markerMap = {{}};
    let legendCollapsed = false;

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
      attribution: 'Tiles &copy; Esri, USDA, USGS',
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

    const openTopo = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: 'Map data &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)',
      maxZoom: 17
    }});

    const osmOutdoors = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }});

    // Global Hiking Trail Overlay (Waymarked Trails)
    const waymarkedTrailsOverlay = L.tileLayer('https://tile.waymarkedtrails.org/hiking/{{z}}/{{x}}/{{y}}.png', {{
      attribution: 'Map &copy; <a href="https://hiking.waymarkedtrails.org">Waymarked Trails</a> (CC-BY-SA)',
      maxZoom: 18,
      opacity: 0.85
    }});

    satelliteHybrid.addTo(map);

    // 3. Boundaries: parks/wilderness and national forests (canvas renderer keeps thousands of vertices fast)
    const polyRenderer = L.canvas({{ padding: 0.3 }});
    function makeBoundaryLayer(filterFn) {{
      const gj = L.geoJSON(parkBoundaries, {{
        renderer: polyRenderer,
        filter: filterFn,
        style: function(feature) {{
          const p = feature.properties;
          const isForest = p.layer === 'forests';
          return {{
            color: p.color || '#10b981',
            weight: (isForest || p.category.includes('Wilderness')) ? 2.0 : 1.8,   // forests match wilderness
            opacity: 0.9,
            fillColor: p.fillColor || '#10b981',
            fillOpacity: p.fillOpacity || 0.18,
            dashArray: p.dashArray || null
          }};
        }},
        onEachFeature: function(feature, layer) {{
          const p = feature.properties;
          const acresStr = p.acres ? `${{Number(p.acres).toLocaleString()}} acres` : '';
          const tooltipContent = `
            <div class="boundary-tooltip">
              <strong>${{p.name}}</strong><br>
              <span style="color:#94a3b8; font-size:10.5px;">${{p.category}} • ${{p.agency}} ${{acresStr ? '• ' + acresStr : ''}}</span>
            </div>
          `;
          layer.bindTooltip(tooltipContent, {{ sticky: true, opacity: 0.95 }});
          layer.on('mouseover', function() {{
            layer.setStyle({{ weight: 3.2, fillOpacity: (p.fillOpacity || 0.18) + 0.12 }});
          }});
          layer.on('mouseout', function() {{
            gj.resetStyle(layer);
          }});
          layer.on('click', function() {{
            map.fitBounds(layer.getBounds(), {{ padding: [40, 40], maxZoom: 12 }});
            selectPark(p);
          }});
        }}
      }});
      return gj;
    }}

    const forestsGeoJson = makeBoundaryLayer(f => f.properties.layer === 'forests');
    forestLayerGroup.addLayer(forestsGeoJson);
    forestLayerGroup.addTo(map);

    const boundariesGeoJson = makeBoundaryLayer(f => f.properties.layer !== 'forests');
    boundaryLayerGroup.addLayer(boundariesGeoJson);
    boundaryLayerGroup.addTo(map);

    // 4. Hiking trails. PCT (gold), JMT (cyan, dashed so the shared PCT tread shows through),
    //    Tahoe Rim Trail (white) get a dark casing; all other hikes are orange.
    const TRAIL_STYLE = {{
      pct:  {{ color: '#facc15', weight: 4.0, dashArray: null }},
      jmt:  {{ color: '#22d3ee', weight: 3.4, dashArray: '9, 7' }},
      trt:  {{ color: '#f8fafc', weight: 3.4, dashArray: null }},
      hike: {{ color: '#f97316', weight: 3.2, dashArray: null }}
    }};
    const trailOrder = {{ hike: 0, pct: 1, trt: 2, jmt: 3 }};   // signature routes drawn on top
    const orderedTrails = {{
      type: 'FeatureCollection',
      features: [...prominentTrails.features].sort((a, b) =>
        (trailOrder[a.properties.trail_type] ?? 0) - (trailOrder[b.properties.trail_type] ?? 0))
    }};

    const trailCasing = L.geoJSON(orderedTrails, {{
      filter: f => f.properties.trail_type !== 'hike',
      interactive: false,
      style: f => ({{ color: '#0f172a', weight: TRAIL_STYLE[f.properties.trail_type].weight + 3, opacity: 0.7 }})
    }});

    const trailsGeoJson = L.geoJSON(orderedTrails, {{
      style: function(feature) {{
        const st = TRAIL_STYLE[feature.properties.trail_type] || TRAIL_STYLE.hike;
        return {{ color: st.color, weight: st.weight, opacity: 0.95, dashArray: st.dashArray, lineCap: 'round' }};
      }},
      onEachFeature: function(feature, layer) {{
        const p = feature.properties;
        const st = TRAIL_STYLE[p.trail_type] || TRAIL_STYLE.hike;
        const tooltipContent = `
          <div class="trail-tooltip" style="border-color:${{st.color}}">
            <strong>${{p.name}}</strong><br>
            <span style="color:#94a3b8; font-size:10.5px;">${{p.park_name}} • ${{p.distance_miles}} • ↑${{p.elevation_gain_ft}}</span><br>
            <span style="color:#fbbf24; font-size:10px; font-weight:600;">Difficulty: ${{p.difficulty}}</span>
          </div>
        `;
        layer.bindTooltip(tooltipContent, {{ sticky: true, opacity: 0.95 }});
        layer.on('mouseover', function() {{
          layer.setStyle({{ weight: st.weight + 2.5, opacity: 1.0 }});
        }});
        layer.on('mouseout', function() {{
          trailsGeoJson.resetStyle(layer);
        }});
        layer.on('click', function() {{
          selectTrail(p);
        }});
      }}
    }});

    trailsLayerGroup.addLayer(trailCasing);
    trailsLayerGroup.addLayer(trailsGeoJson);
    trailsLayerGroup.addTo(map);

    // 5. Peaks & lakes: a fixed-size crosshair centered exactly on the surveyed point,
    //    with the label pinned immediately to its right (no emoji, no offset drift).
    const XHAIR = 18;
    function crosshairSvg(color) {{
      return `<svg width="${{XHAIR}}" height="${{XHAIR}}" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="4.4" fill="none" stroke="#020617" stroke-width="3.6"/>
        <path d="M9 0.5v5M9 12.5v5M0.5 9h5M12.5 9h5" stroke="#020617" stroke-width="3.6" stroke-linecap="round"/>
        <circle cx="9" cy="9" r="4.4" fill="none" stroke="${{color}}" stroke-width="1.8"/>
        <path d="M9 0.5v5M9 12.5v5M0.5 9h5M12.5 9h5" stroke="${{color}}" stroke-width="1.8" stroke-linecap="round"/>
        <circle cx="9" cy="9" r="1.3" fill="${{color}}"/>
      </svg>`;
    }}

    prominentLandmarks.features.forEach(lm => {{
      const p = lm.properties;
      const [lng, lat] = lm.geometry.coordinates;
      const color = p.type === 'peak' ? '#fb7185' : '#38bdf8';
      const elevColor = p.type === 'peak' ? '#fda4af' : '#7dd3fc';
      const elev = p.elevation_ft ? `<span class="lm-elev" style="color:${{elevColor}}">${{Number(p.elevation_ft).toLocaleString()}}'</span>` : '';
      const landmarkIcon = L.divIcon({{
        className: 'landmark-xhair',
        html: `${{crosshairSvg(color)}}<span class="lm-label${{p.major ? '' : ' minor'}}">${{p.name}}${{elev}}</span>`,
        iconSize: [XHAIR, XHAIR],
        iconAnchor: [XHAIR / 2, XHAIR / 2]
      }});

      const marker = L.marker([lat, lng], {{ icon: landmarkIcon, keyboard: false, riseOnHover: true }});
      marker.bindTooltip(`<strong>${{p.name}}</strong><br><span style='font-size:10.5px; color:#cbd5e1;'>${{p.type === 'peak' ? 'Peak' : 'Lake'}} ${{p.elevation_ft ? '• ' + Number(p.elevation_ft).toLocaleString() + ' ft' : ''}}</span>`, {{
        direction: 'top',
        offset: [0, -8],
        className: 'landmark-tooltip'
      }});

      marker.on('click', () => {{
        selectLandmark(p, [lat, lng]);
      }});

      landmarksLayerGroup.addLayer(marker);
    }});

    function updateLandmarkLabelDensity() {{
      map.getContainer().classList.toggle('lm-compact', map.getZoom() < 9);
    }}
    map.on('zoomend', updateLandmarkLabelDensity);
    updateLandmarkLabelDensity();

    landmarksLayerGroup.addTo(map);

    // 6. Rivers: real river centerlines, shown only when zoomed in (RIVER_MIN_ZOOM+), with the river's
    //    name written along its path (SVG textPath, kept upright and re-laid-out after every zoom/pan).
    const riverPane = map.createPane('riverPane');
    riverPane.style.zIndex = 420;            // above park polygons & trails, below markers
    const riverRenderer = L.svg({{ pane: 'riverPane', padding: 0.5 }});
    const RIVER_STYLE = {{ color: '#60a5fa', weight: 2.4, opacity: 0.9 }};
    const riverLines = [];
    riversData.features.forEach(f => {{
      const p = f.properties;
      const parts = f.geometry.type === 'MultiLineString' ? f.geometry.coordinates : [f.geometry.coordinates];
      parts.forEach(part => {{
        const pl = L.polyline(part.map(c => [c[1], c[0]]), {{
          renderer: riverRenderer, noClip: true, smoothFactor: 1.2, lineCap: 'round', ...RIVER_STYLE
        }});
        pl.riverProps = p;
        pl.bindTooltip(`<strong>${{p.name}}</strong><br><span style='font-size:10.5px; color:#cbd5e1;'>River • ${{p.miles_mapped}} mi mapped</span>`, {{
          sticky: true, className: 'landmark-tooltip'
        }});
        pl.on('mouseover', () => pl.setStyle({{ weight: 4.5, color: '#93c5fd' }}));
        pl.on('mouseout', () => pl.setStyle(RIVER_STYLE));
        pl.on('click', e => selectRiver(p, e.latlng));
        riverLines.push(pl);
        riversLayerGroup.addLayer(pl);
      }});
    }});

    const SVG_NS = 'http://www.w3.org/2000/svg';
    let riverLabelGroup = null;

    function slicePolyline(pts, cum, a, b) {{
      // Sub-polyline of pts between arc-length a and b (pixels).
      const out = [];
      const lerp = (i, d) => {{
        const t = (d - cum[i]) / ((cum[i + 1] - cum[i]) || 1);
        return L.point(pts[i].x + (pts[i + 1].x - pts[i].x) * t, pts[i].y + (pts[i + 1].y - pts[i].y) * t);
      }};
      for (let i = 0; i < pts.length - 1; i++) {{
        if (cum[i + 1] < a) continue;
        if (cum[i] > b) break;
        if (!out.length) out.push(lerp(i, Math.max(a, cum[i])));
        if (cum[i + 1] <= b) out.push(pts[i + 1]);
        else {{ out.push(lerp(i, b)); break; }}
      }}
      return out;
    }}

    const _labelCtx = document.createElement('canvas').getContext('2d');
    const _labelWidths = {{}};
    function measureRiverLabel(name) {{
      if (!(name in _labelWidths)) {{
        _labelCtx.font = `italic 700 11px ${{getComputedStyle(document.body).fontFamily}}`;
        _labelWidths[name] = _labelCtx.measureText(name).width + name.length * 0.66;   // + letter-spacing
      }}
      return _labelWidths[name];
    }}

    function smoothForLabel(seg) {{
      // Resample every 3px, then a few moving-average passes so glyphs follow a gentle curve.
      const cum = [0];
      for (let i = 1; i < seg.length; i++) cum.push(cum[i - 1] + seg[i].distanceTo(seg[i - 1]));
      const total = cum[cum.length - 1];
      const pts = [];
      for (let d = 0, j = 0; d <= total; d += 3) {{
        while (j < seg.length - 2 && cum[j + 1] < d) j++;
        const t = (d - cum[j]) / ((cum[j + 1] - cum[j]) || 1);
        pts.push(L.point(seg[j].x + (seg[j + 1].x - seg[j].x) * t, seg[j].y + (seg[j + 1].y - seg[j].y) * t));
      }}
      let cur = pts;
      for (let pass = 0; pass < 3; pass++) {{
        const k = 10;
        cur = cur.map((_, i) => {{
          let sx = 0, sy = 0, n = 0;
          for (let q = Math.max(0, i - k); q <= Math.min(cur.length - 1, i + k); q++) {{ sx += cur[q].x; sy += cur[q].y; n++; }}
          return L.point(sx / n, sy / n);
        }});
      }}
      return cur;
    }}

    function drawRiverLabels() {{
      if (riverLabelGroup) {{ riverLabelGroup.remove(); riverLabelGroup = null; }}
      if (!map.hasLayer(riversLayerGroup) || !riverRenderer._rootGroup) return;
      riverLabelGroup = document.createElementNS(SVG_NS, 'g');
      riverRenderer._rootGroup.appendChild(riverLabelGroup);
      const view = map.getBounds();
      const vb = L.bounds(map.latLngToLayerPoint(view.getNorthWest()), map.latLngToLayerPoint(view.getSouthEast()));
      let uid = 0;
      riverLines.forEach(pl => {{
        if (!view.intersects(pl.getBounds())) return;
        const name = pl.riverProps.name;
        const textW = measureRiverLabel(name) + 12;
        (pl._parts || []).forEach(pts => {{
          if (pts.length < 2) return;
          const cum = [0];
          for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + pts[i].distanceTo(pts[i - 1]));
          const total = cum[cum.length - 1];
          if (total < textW + 40) return;
          let lastPlaced = -Infinity;
          for (let c = textW / 2 + 30; c < total - textW / 2 - 30; c += 40) {{
            if (c - lastPlaced < 420) continue;
            const a = c - textW / 2, b = c + textW / 2;
            let seg = slicePolyline(pts, cum, a - 30, b + 30);
            if (seg.length < 2) continue;
            if (!vb.contains(seg[Math.floor(seg.length / 2)])) continue;
            if (seg[0].distanceTo(seg[seg.length - 1]) < 0.75 * (textW + 60)) continue;   // too curvy here
            seg = smoothForLabel(seg);
            if (seg[seg.length - 1].x < seg[0].x) seg = seg.reverse();                    // keep text upright
            const id = `river-lbl-${{uid++}}`;
            const path = document.createElementNS(SVG_NS, 'path');
            path.setAttribute('id', id);
            path.setAttribute('d', 'M' + seg.map(q => `${{q.x.toFixed(1)}} ${{q.y.toFixed(1)}}`).join(' L'));
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', 'none');
            const text = document.createElementNS(SVG_NS, 'text');
            text.setAttribute('class', 'river-label');
            text.setAttribute('dy', '-5');
            const tp = document.createElementNS(SVG_NS, 'textPath');
            tp.setAttribute('href', '#' + id);
            tp.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', '#' + id);
            tp.setAttribute('startOffset', '50%');
            tp.setAttribute('text-anchor', 'middle');
            tp.textContent = name;
            text.appendChild(tp);
            riverLabelGroup.appendChild(path);
            riverLabelGroup.appendChild(text);
            lastPlaced = c;
          }}
        }});
      }});
    }}

    let riverLabelFrame = null;
    function scheduleRiverLabels() {{
      // Lay labels out on the next frame, after Leaflet has finished re-projecting every river path.
      if (riverLabelFrame) cancelAnimationFrame(riverLabelFrame);
      riverLabelFrame = requestAnimationFrame(() => {{ riverLabelFrame = null; drawRiverLabels(); }});
    }}

    let riversEnabled = true;
    let riverLabelHook = false;
    function updateRivers() {{
      const want = riversEnabled && map.getZoom() >= RIVER_MIN_ZOOM;
      if (want && !map.hasLayer(riversLayerGroup)) map.addLayer(riversLayerGroup);
      if (!want && map.hasLayer(riversLayerGroup)) map.removeLayer(riversLayerGroup);
      if (!riverLabelHook && map.hasLayer(riversLayerGroup)) {{
        // Re-layout labels whenever the SVG renderer has re-projected the river paths (after every zoom/pan).
        riverRenderer.on('update', scheduleRiverLabels);
        riverLabelHook = true;
      }}
      scheduleRiverLabels();
    }}
    riversToggle.addTo(map);
    map.on('moveend', updateRivers);
    map.on('viewreset zoomend', scheduleRiverLabels);
    map.on('overlayadd', e => {{ if (e.layer === riversToggle) {{ riversEnabled = true; updateRivers(); }} }});
    map.on('overlayremove', e => {{ if (e.layer === riversToggle) {{ riversEnabled = false; updateRivers(); }} }});

    // 7. American River whitewater rafting runs
    raftingData.features.forEach(f => {{
      const p = f.properties;
      const latlngs = f.geometry.coordinates.map(c => [c[1], c[0]]);
      L.polyline(latlngs, {{ color: '#0f172a', weight: 10, opacity: 0.7, interactive: false, lineCap: 'round' }}).addTo(raftingLayerGroup);
      const line = L.polyline(latlngs, {{ color: '#2dd4bf', weight: 6, opacity: 0.95, lineCap: 'round' }});
      const foam = L.polyline(latlngs, {{ color: '#f0fdfa', weight: 2, opacity: 0.9, dashArray: '2, 11', interactive: false }});
      line.bindTooltip(`
        <div class="raft-label">
          <strong>${{p.name}}</strong><br>
          <span style="color:#5eead4; font-weight:700;">${{p['class']}}</span>
          <span style="color:#94a3b8; font-size:10.5px;"> • ${{p.length_miles}} mi • ${{p.put_in}} → ${{p.take_out}}</span><br>
          <span style="color:#cbd5e1; font-size:10px;">${{p.season}}</span>
        </div>`, {{ sticky: true, opacity: 0.97 }});
      line.on('mouseover', () => line.setStyle({{ weight: 8.5 }}));
      line.on('mouseout', () => line.setStyle({{ weight: 6 }}));
      line.on('click', () => selectRafting(p));
      line.addTo(raftingLayerGroup);
      foam.addTo(raftingLayerGroup);
      [[p.put_in_coords, '#22c55e', 'Put-in', p.put_in], [p.take_out_coords, '#ef4444', 'Take-out', p.take_out]].forEach(([c, col, kind, label]) => {{
        L.circleMarker([c[1], c[0]], {{ radius: 5.5, color: '#ffffff', weight: 2, fillColor: col, fillOpacity: 1 }})
          .bindTooltip(`<strong>${{kind}}:</strong> ${{label}}<br><span style='font-size:10.5px;color:#94a3b8'>${{p.name}}</span>`, {{ direction: 'top', offset: [0, -6] }})
          .on('click', () => selectRafting(p))
          .addTo(raftingLayerGroup);
      }});
    }});
    raftingLayerGroup.addTo(map);

    markerLayerGroup.addTo(map);
    ringsLayerGroup.addTo(map);

    // Layer Controls
    const baseLayers = {{
      "🛰️ Satellite + Major Roads (Default)": satelliteHybrid,
      "🌲 USGS Topo & Land Cover": usgsTopo,
      "🏔️ OpenTopoMap (Contours & Relief)": openTopo,
      "🗺️ Street & Outdoors (OSM)": osmOutdoors
    }};
    const overlayLayers = {{
      "🌲 Park & Wilderness Boundaries": boundaryLayerGroup,
      "🌳 National Forests": forestLayerGroup,
      "🥾 Hiking Trails (PCT, JMT, TRT & hikes)": trailsLayerGroup,
      "🌐 Waymarked Trails (Global Hiking Overlay)": waymarkedTrailsOverlay,
      "⌖ Peaks & Lakes": landmarksLayerGroup,
      "〰 Rivers (zoom 10+)": riversToggle,
      "🛶 American River Rafting Runs": raftingLayerGroup,
      "📍 Campsite Markers": markerLayerGroup,
      "⭕ Distance Rings": ringsLayerGroup
    }};
    L.control.layers(baseLayers, overlayLayers, {{ position: 'topleft' }}).addTo(map);

    function getAgencyColor(agency, name = "") {{
      if (agency.includes("National Park") || agency.includes("NPS")) return "#38bdf8"; // sky blue
      if (agency.includes("State Park") || agency.includes("State Rec") || agency.includes("Nevada State")) return "#34d399"; // emerald green
      if (agency.includes("Wilderness") || name.includes("Wilderness")) return "#c084fc"; // purple
      if (agency.includes("Forest") || agency.includes("BLM")) return "#fbbf24"; // amber
      return "#f472b6"; // pink for regional/county
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
        const color = getAgencyColor(cg.agency, cg.name);
        const isSelected = cg.id === selectedId;

        const marker = L.circleMarker([cg.lat, cg.lng], {{
          radius: isSelected ? 7.5 : 5.5,
          fillColor: color,
          color: isSelected ? '#ffffff' : '#0f172a',
          weight: isSelected ? 2.5 : 1.2,
          fillOpacity: 0.95
        }});

        marker.bindTooltip(`<strong>${{cg.name}}</strong><br><span style='font-size:11px;color:#94a3b8'>${{cg.park_name}} • ${{cg.drive_time_from_home}} (${{cg.distance_road_miles}} mi) • ${{cg.reservation_type}}</span>`, {{
          direction: 'top',
          offset: [0, -6]
        }});

        const popupContent = `
          <div style="font-size:12px; min-width:210px;">
            <div style="font-weight:bold; font-size:13px; color:#ffffff; margin-bottom:2px;">${{cg.name}}</div>
            <div style="color:#94a3b8; font-size:11px; margin-bottom:6px;">${{cg.park_name}} • ${{cg.agency}}</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <span style="color:#cbd5e1">Drive from Home:</span>
              <strong style="color:#38bdf8">${{cg.drive_time_from_home}}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <span style="color:#cbd5e1">Capacity:</span>
              <span style="color:#f8fafc; font-weight:600">${{cg.num_sites}} sites</span>
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

      // Restore campground labels
      document.getElementById("card-region").textContent = cg.region;
      document.getElementById("card-park-badge").textContent = cg.park_name;
      document.getElementById("card-title").textContent = cg.name;
      document.getElementById("card-agency").textContent = cg.agency;
      document.getElementById("card-score").textContent = cg.composite_score_out_of_10.toFixed(1);
      document.getElementById("card-score-label").textContent = "Composite / 10";
      
      document.getElementById("card-metrics-title").textContent = "Multi-Field Assessment";
      document.getElementById("card-comp-badge").textContent = `Competition: ${{cg.competition_badge || (cg.rating_competition + '/10')}}`;
      document.getElementById("metric-label-1").textContent = "🥾 Hiking";
      document.getElementById("card-rating-hiking").textContent = `${{cg.rating_hiking.toFixed(1)}} / 10`;
      document.getElementById("metric-label-2").textContent = "🌅 Views";
      document.getElementById("card-rating-views").textContent = `${{cg.rating_views.toFixed(1)}} / 10`;
      document.getElementById("metric-label-3").textContent = "⛺ Comfort";
      document.getElementById("card-rating-comfort").textContent = `${{cg.rating_comfort.toFixed(1)}} / 10`;

      document.getElementById("card-stat1-label").textContent = "Drive from Home";
      document.getElementById("card-drive").textContent = `${{cg.drive_time_from_home}} (~${{cg.distance_road_miles}} mi)`;
      document.getElementById("card-stat2-label").textContent = "Specific Capacity";
      document.getElementById("card-capacity").textContent = `${{cg.num_sites}} sites (${{cg.site_types}})`;

      document.getElementById("card-seasonal-box").style.display = "block";
      document.getElementById("card-peak-season").textContent = cg.peak_season || "Jun – Sep";
      document.getElementById("card-light-season").textContent = cg.light_season || "Nov – Apr";
      document.getElementById("card-winter-profile").textContent = cg.winter_profile || "Open with winter weather variations.";

      document.getElementById("card-reservation-box").style.display = "block";
      document.getElementById("card-rule-title").textContent = cg.reservation_type;
      document.getElementById("card-window").textContent = cg.reservation_window;
      document.getElementById("card-fee-label").textContent = "Nightly Fee:";
      document.getElementById("card-fee").textContent = cg.nightly_fee;

      document.getElementById("card-hikes-title").textContent = "Direct Trailheads & Nearby Attractions";
      document.getElementById("card-hikes-icon").textContent = "🥾";
      document.getElementById("card-hikes").textContent = cg.nearby_hikes_attractions;

      document.getElementById("card-reserve-btn").href = cg.direct_booking_url;
      document.getElementById("card-reserve-btn").style.display = "flex";
      document.getElementById("card-btn1-text").textContent = "Reserve Campsite Page ↗";

      document.getElementById("card-inspect-btn").href = cg.overview_url;
      document.getElementById("card-btn2-text").textContent = "Park Overview & Hikes ↗";
      
      const mapsQuery = encodeURIComponent(`${{cg.name}}, ${{cg.park_name}}, California`);
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
        if (markerMap[key]) {{
          markerMap[key].setStyle({{
            radius: isCurrent ? 7.5 : 5.5,
            color: isCurrent ? '#ffffff' : '#0f172a',
            weight: isCurrent ? 2.5 : 1.2
          }});
        }}
      }});
    }}

    function selectTrail(p) {{
      document.getElementById("card-region").textContent = "Hiking Trail";
      document.getElementById("card-park-badge").textContent = p.park_name;
      document.getElementById("card-title").textContent = p.name;
      document.getElementById("card-agency").textContent = p.category;
      document.getElementById("card-score").textContent = "🥾";
      document.getElementById("card-score-label").textContent = p.difficulty;

      document.getElementById("card-metrics-title").textContent = "Trail Specifications";
      document.getElementById("card-comp-badge").textContent = `Difficulty: ${{p.difficulty}}`;
      document.getElementById("metric-label-1").textContent = "📏 Distance";
      document.getElementById("card-rating-hiking").textContent = p.distance_miles;
      document.getElementById("metric-label-2").textContent = "📈 Elevation Gain";
      document.getElementById("card-rating-views").textContent = `↑ ${{p.elevation_gain_ft}}`;
      document.getElementById("metric-label-3").textContent = "⛺ Trailhead Camp";
      document.getElementById("card-rating-comfort").textContent = p.trailhead_campground ? p.trailhead_campground.split("/")[0].trim() : "Nearby";

      document.getElementById("card-stat1-label").textContent = "Distance & Gain";
      document.getElementById("card-drive").textContent = `${{p.distance_miles}} (Gain: ${{p.elevation_gain_ft}})`;
      document.getElementById("card-stat2-label").textContent = "Trailhead Camp";
      document.getElementById("card-capacity").textContent = p.trailhead_campground || p.park_name;

      document.getElementById("card-seasonal-box").style.display = "block";
      document.getElementById("card-peak-season").textContent = "Spring to Autumn (Alpine: Jul - Sep)";
      document.getElementById("card-light-season").textContent = "Winter snows (snowshoe/skis)";
      document.getElementById("card-winter-profile").textContent = "Trail conditions change rapidly in winter; check ranger stations for snowpack, microspikes or avalanche risk.";

      document.getElementById("card-reservation-box").style.display = "none";

      document.getElementById("card-hikes-title").textContent = "Trail Route & Guide";
      document.getElementById("card-hikes-icon").textContent = "🗺️";
      document.getElementById("card-hikes").textContent = p.description;

      document.getElementById("card-reserve-btn").style.display = "none";
      document.getElementById("card-inspect-btn").href = `https://www.alltrails.com/search?q=${{encodeURIComponent(p.name + ' ' + p.park_name)}}`;
      document.getElementById("card-btn2-text").textContent = "AllTrails Route Info ↗";

      const mapsQuery = encodeURIComponent(`${{p.name}}, ${{p.park_name}}, California`);
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/search/${{mapsQuery}}`;
    }}

    function selectLandmark(p, coords) {{
      const typeIcons = {{ peak: "▲", lake: "◉", river: "〰" }};
      const icon = typeIcons[p.type] || "⌖";
      
      document.getElementById("card-region").textContent = p.type.toUpperCase();
      document.getElementById("card-park-badge").textContent = p.elevation_ft ? `${{Number(p.elevation_ft).toLocaleString()}} ft elevation` : "California Waterway";
      document.getElementById("card-title").textContent = p.name;
      document.getElementById("card-agency").textContent = p.type === "peak" ? "Mountain Peak" : (p.type === "lake" ? "Alpine / Natural Lake" : "River / Waterway");
      document.getElementById("card-score").textContent = icon;
      document.getElementById("card-score-label").textContent = p.type.toUpperCase();

      document.getElementById("card-metrics-title").textContent = "Landmark Intelligence";
      document.getElementById("card-comp-badge").textContent = p.elevation_ft ? `Elevation: ${{Number(p.elevation_ft).toLocaleString()}}'` : "Natural Landmark";
      document.getElementById("metric-label-1").textContent = "Feature Type";
      document.getElementById("card-rating-hiking").textContent = p.type.toUpperCase();
      document.getElementById("metric-label-2").textContent = "Elevation";
      document.getElementById("card-rating-views").textContent = p.elevation_ft ? `${{Number(p.elevation_ft).toLocaleString()}} ft` : "Sea Level to Crest";
      document.getElementById("metric-label-3").textContent = "Coordinates";
      document.getElementById("card-rating-comfort").textContent = `${{coords[0].toFixed(2)}}°, ${{coords[1].toFixed(2)}}°`;

      document.getElementById("card-stat1-label").textContent = "Landmark";
      document.getElementById("card-drive").textContent = p.name;
      document.getElementById("card-stat2-label").textContent = "Elevation (ft)";
      document.getElementById("card-capacity").textContent = p.elevation_ft ? `${{Number(p.elevation_ft).toLocaleString()}} feet` : "Natural waterway";

      document.getElementById("card-seasonal-box").style.display = "none";
      document.getElementById("card-reservation-box").style.display = "none";

      document.getElementById("card-hikes-title").textContent = "Geographic & Scenic Summary";
      document.getElementById("card-hikes-icon").textContent = icon;
      document.getElementById("card-hikes").textContent = p.description;

      document.getElementById("card-reserve-btn").style.display = "none";
      document.getElementById("card-inspect-btn").href = `https://en.wikipedia.org/wiki/${{encodeURIComponent(p.name.split('(')[0].trim())}}`;
      document.getElementById("card-btn2-text").textContent = "Wikipedia Geography ↗";

      const mapsQuery = encodeURIComponent(`${{p.name}}, California`);
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/search/${{mapsQuery}}`;

      map.panTo(coords, {{ animate: true, duration: 0.5 }});
    }}

    function selectRiver(p, latlng) {{
      selectLandmark({{ ...p, elevation_ft: null }}, [latlng.lat, latlng.lng]);
      document.getElementById("card-park-badge").textContent = `${{p.miles_mapped}} mi mapped`;
      document.getElementById("card-capacity").textContent = `${{p.miles_mapped}} river miles mapped`;
    }}

    function selectRafting(p) {{
      document.getElementById("card-region").textContent = "Whitewater Rafting";
      document.getElementById("card-park-badge").textContent = p.river;
      document.getElementById("card-title").textContent = p.name;
      document.getElementById("card-agency").textContent = `${{p.put_in}} → ${{p.take_out}}`;
      document.getElementById("card-score").textContent = p['class'].replace('Class ', '');
      document.getElementById("card-score-label").textContent = "Whitewater Class";

      document.getElementById("card-metrics-title").textContent = "Run Specifications";
      document.getElementById("card-comp-badge").textContent = p['class'];
      document.getElementById("metric-label-1").textContent = "Length";
      document.getElementById("card-rating-hiking").textContent = `${{p.length_miles}} mi`;
      document.getElementById("metric-label-2").textContent = "Difficulty";
      document.getElementById("card-rating-views").textContent = p['class'];
      document.getElementById("metric-label-3").textContent = "Season";
      document.getElementById("card-rating-comfort").textContent = p.season.split('(')[0].trim();

      document.getElementById("card-stat1-label").textContent = "Put-in";
      document.getElementById("card-drive").textContent = p.put_in;
      document.getElementById("card-stat2-label").textContent = "Take-out";
      document.getElementById("card-capacity").textContent = p.take_out;

      document.getElementById("card-seasonal-box").style.display = "block";
      document.getElementById("card-peak-season").textContent = p.season;
      document.getElementById("card-light-season").textContent = "Check flows (CDEC / Dreamflows) before launching";
      document.getElementById("card-winter-profile").textContent = "Cold snowmelt and fast flows: go with a licensed outfitter unless you have Class-appropriate experience, PFD, helmet and rescue skills.";

      document.getElementById("card-reservation-box").style.display = "none";

      document.getElementById("card-hikes-title").textContent = "Run Description";
      document.getElementById("card-hikes-icon").textContent = "🛶";
      document.getElementById("card-hikes").textContent = p.description;

      document.getElementById("card-reserve-btn").style.display = "none";
      document.getElementById("card-inspect-btn").href = `https://www.google.com/search?q=${{encodeURIComponent(p.name + ' rafting')}}`;
      document.getElementById("card-btn2-text").textContent = "Outfitters & Flows ↗";

      const [lng, lat] = p.put_in_coords;
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/dir/Grace+Cathedral,+1100+California+St,+San+Francisco,+CA+94108/${{lat}},${{lng}}`;
    }}

    function selectPark(p) {{
      document.getElementById("card-region").textContent = p.category || "Park Area";
      document.getElementById("card-park-badge").textContent = p.acres ? `${{Number(p.acres).toLocaleString()}} acres` : "Public Lands";
      document.getElementById("card-title").textContent = p.name;
      document.getElementById("card-agency").textContent = p.agency || "Managing Agency";
      document.getElementById("card-score").textContent = "🌲";
      document.getElementById("card-score-label").textContent = p.category || "Park Area";

      // Match all campgrounds in this park without hiding ANY campgrounds on the map!
      const pNameLower = p.name.toLowerCase();
      const parkCgs = campgrounds.filter(c => {{
        const cPark = (c.park_name || "").toLowerCase();
        const cName = (c.name || "").toLowerCase();
        return cPark.includes(pNameLower) || pNameLower.includes(cPark) || cName.includes(pNameLower);
      }});

      document.getElementById("card-metrics-title").textContent = "Park Information & Capacity";
      document.getElementById("card-comp-badge").textContent = `${{parkCgs.length}} Campsites in Area`;
      document.getElementById("metric-label-1").textContent = "Jurisdiction";
      document.getElementById("card-rating-hiking").textContent = p.category ? p.category.split('/')[0].trim() : "Protected";
      document.getElementById("metric-label-2").textContent = "Acreage";
      document.getElementById("card-rating-views").textContent = p.acres ? `${{Number(p.acres).toLocaleString()}} ac` : "Surveyed";
      document.getElementById("metric-label-3").textContent = "Campgrounds";
      document.getElementById("card-rating-comfort").textContent = `${{parkCgs.length}} sites`;

      document.getElementById("card-stat1-label").textContent = "Managing Agency";
      document.getElementById("card-drive").textContent = p.agency || "Public Agency";
      document.getElementById("card-stat2-label").textContent = "Campgrounds in Park";
      document.getElementById("card-capacity").textContent = parkCgs.length > 0 ? `${{parkCgs.length}} campgrounds available` : "Backcountry / Wilderness";

      document.getElementById("card-seasonal-box").style.display = "block";
      document.getElementById("card-peak-season").textContent = "Summer & Fall";
      document.getElementById("card-light-season").textContent = "Winter & Early Spring";
      document.getElementById("card-winter-profile").textContent = "High-resolution vector boundary active. All regional campgrounds remain visible across the map. Check Caltrans and agency pages for current seasonal conditions.";

      document.getElementById("card-reservation-box").style.display = "none";

      document.getElementById("card-hikes-title").textContent = "Park Geography & Features";
      document.getElementById("card-hikes-icon").textContent = "🌲";
      const cgNamesList = parkCgs.map(c => c.name).join(", ");
      document.getElementById("card-hikes").textContent = `${{p.description || "Public protected outdoor park."}} ${{parkCgs.length > 0 ? "Campgrounds: " + cgNamesList + "." : ""}}`;

      document.getElementById("card-reserve-btn").style.display = "none";
      document.getElementById("card-inspect-btn").href = `https://www.google.com/search?q=${{encodeURIComponent(p.name + ' California Parks')}}`;
      document.getElementById("card-btn2-text").textContent = "Search Park Info ↗";

      const mapsQuery = encodeURIComponent(`${{p.name}}, California`);
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/search/${{mapsQuery}}`;

      // Highlight this park's campgrounds with a golden ring while keeping ALL other campgrounds 100% visible!
      const parkCgIds = new Set(parkCgs.map(c => c.id));
      Object.keys(markerMap).forEach(key => {{
        const isParkCg = parkCgIds.has(key);
        if (markerMap[key]) {{
          markerMap[key].setStyle({{
            radius: isParkCg ? 8.5 : 5.5,
            color: isParkCg ? '#fbbf24' : '#0f172a',
            weight: isParkCg ? 3.0 : 1.2
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
            <span class="w-2.5 h-2.5 rounded-full inline-block flex-shrink-0" style="background-color: ${{getAgencyColor(cg.agency, cg.name)}}"></span>
            <span>${{cg.name}}</span>
          </td>
          <td class="py-3 px-3 text-slate-300 whitespace-nowrap">${{cg.park_name}}</td>
          <td class="py-3 px-3 text-slate-400 whitespace-nowrap">${{cg.region}}</td>
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
          <td class="py-3 px-3 text-slate-300 font-semibold whitespace-nowrap">${{cg.num_sites}} sites</td>
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
          cg.park_name.toLowerCase().includes(query) ||
          cg.nearby_hikes_attractions.toLowerCase().includes(query) ||
          cg.region.toLowerCase().includes(query) ||
          (cg.description && cg.description.toLowerCase().includes(query)) ||
          (cg.winter_profile && cg.winter_profile.toLowerCase().includes(query));

        let matchesRegion = (region === "ALL");
        if (!matchesRegion) {{
          matchesRegion = (cg.region === region) || 
            (region === "East Bay" && (cg.region.includes("East Bay") || cg.park_name.includes("Diablo"))) ||
            (region === "Sonoma / Coast" && (cg.region.includes("Coast") && cg.region.includes("Sonoma")));
        }}
        
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


print(f"Generated campground_map_dashboard.html ({len(html_content):,} bytes)")
