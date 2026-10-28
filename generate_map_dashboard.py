import json
import math

with open("campgrounds_data.json", "r") as f:
    data = json.load(f)

campgrounds = data["campgrounds"]
home = data["home_point"]

# Bounds for Northern & Central California map projection
# Lat: 35.5 (south of Big Sur) to 41.5 (north of Mt Shasta / Castle Crags)
# Lng: -124.5 (Pacific Coast) to -119.2 (Yosemite / High Sierra)
MIN_LAT = 35.4
MAX_LAT = 41.6
MIN_LNG = -124.4
MAX_LNG = -119.0

MAP_WIDTH = 960
MAP_HEIGHT = 800

def project(lat, lng):
    # Mercator approximation
    x = (lng - MIN_LNG) / (MAX_LNG - MIN_LNG) * MAP_WIDTH
    # Invert Y because SVG coordinates go down
    y = (MAX_LAT - lat) / (MAX_LAT - MIN_LAT) * MAP_HEIGHT
    return round(x, 1), round(y, 1)

home_x, home_y = project(home["lat"], home["lng"])

# Enrich each campground with SVG coords
for c in campgrounds:
    cx, cy = project(c["lat"], c["lng"])
    c["svg_x"] = cx
    c["svg_y"] = cy

campgrounds_json_str = json.dumps(campgrounds)
home_json_str = json.dumps(home)

html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NorCal & Bay Area Campground Intelligence Map</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .map-container {{
      position: relative;
      background: radial-gradient(circle at 50% 50%, #1e293b 0%, #0f172a 100%);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }}
    .ring-line {{
      stroke: rgba(148, 163, 184, 0.22);
      stroke-dasharray: 4, 4;
      fill: none;
    }}
    .ring-label {{
      fill: #94a3b8;
      font-size: 11px;
      font-weight: 500;
    }}
    .cg-marker {{
      cursor: pointer;
      transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.2s ease;
    }}
    .cg-marker:hover {{
      transform: scale(1.45);
      filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.8));
    }}
    .active-marker {{
      stroke: #ffffff !important;
      stroke-width: 3px !important;
      transform: scale(1.6);
      filter: drop-shadow(0 0 12px #38bdf8) !important;
    }}
    /* Custom scrollbar */
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
    <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
      <div>
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            SF Outdoor Operations
          </span>
          <span class="text-xs text-slate-400">Home Anchor: <strong>Grace Cathedral (Nob Hill, SF)</strong></span>
        </div>
        <h1 class="text-3xl font-extrabold tracking-tight text-white mt-1">
          California Campgrounds & Wilderness Explorer
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          Visualizing 43 premier campgrounds across the Greater Bay Area, North Coast, Sonoma/Napa, Big Sur, Shasta-Cascade, and Sierra Nevada.
        </p>
      </div>

      <!-- Quick Metrics -->
      <div class="flex items-center gap-3">
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-white" id="stat-total">43</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">Campgrounds</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-amber-400">8 AM</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">State Parks Drop</span>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-center">
          <span class="block text-2xl font-bold text-sky-400">7 AM</span>
          <span class="text-[11px] text-slate-400 uppercase tracking-wider">NPS/USFS Drop</span>
        </div>
      </div>
    </header>

    <!-- Controls & Filters Bar -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
      <!-- Search -->
      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1">Search Campground or Trail</label>
        <input 
          id="search-input" 
          type="text" 
          placeholder="e.g. Alamere, Big Sur, FCFS..." 
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
          <option value="ALL">All Regions (NorCal Overview)</option>
          <option value="San Francisco">San Francisco & Immediate</option>
          <option value="Marin / SF Bay">Marin & Point Reyes</option>
          <option value="East Bay">East Bay Regional Parks</option>
          <option value="Half Moon Bay / Coast">Half Moon Bay & Coast</option>
          <option value="Santa Cruz Mountains">Santa Cruz Redwoods</option>
          <option value="Sonoma / Napa">Sonoma & Napa Valley</option>
          <option value="Monterey Bay & Big Sur">Monterey Bay & Big Sur</option>
          <option value="Shasta / Trinity / Cascade">Shasta-Cascade & Trinity Alps</option>
          <option value="Sierra Nevada">Sierra Nevada & Tahoe / Yosemite</option>
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
          <option value="California State Parks">California State Parks</option>
          <option value="US Forest Service">US Forest Service (USFS) / BLM</option>
          <option value="Regional">Regional & County Parks (EBRPD, San Mateo)</option>
        </select>
      </div>
    </div>

    <!-- Map & Detail Panel Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      
      <!-- Interactive SVG Map (8 cols on large screens) -->
      <div class="lg:col-span-8 map-container p-2 relative">
        <!-- Floating Map Legend -->
        <div class="absolute top-4 left-4 z-10 bg-slate-900/85 backdrop-blur-md border border-slate-700/60 rounded-xl p-3 text-xs shadow-lg space-y-1.5">
          <div class="font-bold text-white text-[13px] border-b border-slate-700 pb-1 flex items-center justify-between gap-4">
            <span>Map Legend</span>
            <span class="text-[11px] font-normal text-slate-400">Click dot for details</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3.5 h-3.5 rounded-full bg-rose-500 inline-block ring-2 ring-rose-400/40"></span>
            <span class="text-slate-300">Grace Cathedral (Home Base)</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>
            <span class="text-slate-300">California State Parks (ReserveCal)</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-sky-400 inline-block"></span>
            <span class="text-slate-300">National Parks / Rec Areas (Rec.gov)</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-amber-400 inline-block"></span>
            <span class="text-slate-300">USFS / BLM / Dispersed / Free</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-purple-400 inline-block"></span>
            <span class="text-slate-300">Regional / County Parks</span>
          </div>
          <div class="pt-1 text-[11px] text-slate-400 border-t border-slate-800">
            Rings = 25mi, 50mi, 100mi, 200mi radius
          </div>
        </div>

        <!-- SVG Visual Canvas -->
        <svg id="ca-map" viewBox="0 0 960 800" class="w-full h-auto select-none">
          <!-- Coastline Background Shading -->
          <!-- Pacific Ocean -->
          <path d="M 0,0 L 260,0 L 285,100 L 290,190 L 320,310 L 335,340 L 350,380 L 380,480 L 410,540 L 450,620 L 510,700 L 590,800 L 0,800 Z" fill="#091322" opacity="0.6"/>
          
          <!-- Distance Rings from Grace Cathedral -->
          <!-- 25 Miles Straight (~50px at scale) -->
          <circle cx="{home_x}" cy="{home_y}" r="45" class="ring-line"/>
          <text x="{home_x + 47}" y="{home_y - 8}" class="ring-label">25 mi</text>

          <!-- 50 Miles Straight (~90px at scale) -->
          <circle cx="{home_x}" cy="{home_y}" r="90" class="ring-line"/>
          <text x="{home_x + 92}" y="{home_y - 8}" class="ring-label">50 mi</text>

          <!-- 100 Miles Straight (~180px at scale) -->
          <circle cx="{home_x}" cy="{home_y}" r="180" class="ring-line"/>
          <text x="{home_x + 182}" y="{home_y - 8}" class="ring-label">100 mi</text>

          <!-- 200 Miles Straight (~360px at scale) -->
          <circle cx="{home_x}" cy="{home_y}" r="360" class="ring-line"/>
          <text x="{home_x + 362}" y="{home_y - 8}" class="ring-label">200 mi</text>

          <!-- Stylized Geographic Landmarks / Labels -->
          <g opacity="0.4" font-size="11" fill="#64748b" font-weight="600" text-anchor="middle">
            <text x="540" y="80">MT. SHASTA & CASCADE CREST</text>
            <text x="360" y="140">TRINITY ALPS WILDERNESS</text>
            <text x="750" y="270">LASSEN VOLCANIC</text>
            <text x="720" y="440">LAKE TAHOE</text>
            <text x="780" y="560">YOSEMITE & SIERRA</text>
            <text x="180" y="320">PACIFIC OCEAN</text>
            <text x="320" y="380">POINT REYES</text>
            <text x="490" y="580">BIG SUR COAST</text>
            <text x="590" y="520">PINNACLES</text>
          </g>

          <!-- Home Base Marker (Grace Cathedral) -->
          <g transform="translate({home_x}, {home_y})">
            <!-- Pulsing outer circle -->
            <circle r="12" fill="none" stroke="#f43f5e" stroke-width="2" opacity="0.6">
              <animate attributeName="r" values="8;18;8" dur="3s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.8;0;0.8" dur="3s" repeatCount="indefinite"/>
            </circle>
            <circle r="7" fill="#f43f5e" stroke="#ffffff" stroke-width="2"/>
            <text x="12" y="4" fill="#f43f5e" font-size="12" font-weight="bold">Grace Cathedral (SF)</text>
          </g>

          <!-- Campground Markers Dynamic Container -->
          <g id="campground-markers"></g>
        </svg>
      </div>

      <!-- Detail Card & Inspector Panel (4 cols on large screens) -->
      <div class="lg:col-span-4 space-y-4">
        <!-- Selected Card Detail -->
        <div id="detail-card" class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div class="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <span id="card-region" class="px-2 py-0.5 text-[11px] font-semibold rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
                Region
              </span>
              <h2 id="card-title" class="text-xl font-bold text-white mt-1.5 leading-snug">
                Click any campground on map
              </h2>
              <p id="card-agency" class="text-xs text-slate-400">Managing Agency</p>
            </div>
            <div class="text-right">
              <div class="bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-2.5 py-1 text-center">
                <span id="card-score" class="text-lg font-black text-emerald-400">9.8</span>
                <span class="block text-[9px] uppercase tracking-wider text-slate-400">Score / 10</span>
              </div>
            </div>
          </div>

          <!-- Quick Stats Grid -->
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-800/60 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase">Drive from Grace Cath.</span>
              <span id="card-drive" class="font-semibold text-white text-sm">45 mins (21 mi)</span>
            </div>
            <div class="bg-slate-800/60 rounded-lg p-2.5 border border-slate-800">
              <span class="block text-slate-400 text-[10px] uppercase">Capacity</span>
              <span id="card-capacity" class="font-semibold text-white text-sm">31 campsites</span>
            </div>
          </div>

          <!-- Reservation Intelligence Callout -->
          <div class="bg-amber-950/30 border border-amber-600/40 rounded-xl p-3.5 space-y-1.5">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-amber-400"></span>
              <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider" id="card-rule-title">Reservation Rule & Window</h3>
            </div>
            <p class="text-xs text-amber-100/90 leading-relaxed" id="card-window">
              Select a campground to see exact release dates and booking system (ReserveCalifornia, Recreation.gov, or FCFS).
            </p>
            <div class="pt-1 flex items-center justify-between text-[11px] text-amber-200/70 border-t border-amber-900/50">
              <span>Nightly Fee:</span>
              <strong id="card-fee" class="text-white">$35 / night</strong>
            </div>
          </div>

          <!-- Hikes & Attractions -->
          <div class="space-y-1.5">
            <h4 class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
              <span>🥾</span> Nearby Well-Rated Hikes & Attractions
            </h4>
            <p id="card-hikes" class="text-xs text-slate-400 bg-slate-800/50 p-2.5 rounded-lg border border-slate-800 leading-relaxed">
              Nearby hiking trails and natural landmarks.
            </p>
          </div>

          <!-- Description -->
          <div class="space-y-1">
            <h4 class="text-xs font-bold text-slate-300">About this Destination</h4>
            <p id="card-desc" class="text-xs text-slate-400 leading-relaxed">
              Description and tactical advice.
            </p>
          </div>

          <!-- External Actions -->
          <div class="pt-2 border-t border-slate-800 flex items-center gap-2">
            <a id="card-google-maps" href="#" target="_blank" class="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-center py-2 px-3 rounded-lg text-xs font-medium transition">
              Directions on Maps ↗
            </a>
            <a id="card-booking-link" href="#" target="_blank" class="flex-1 bg-sky-600 hover:bg-sky-500 text-white text-center py-2 px-3 rounded-lg text-xs font-semibold transition">
              Booking Portal ↗
            </a>
          </div>
        </div>

        <!-- Quick Strategy Cheat Sheet -->
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs space-y-2.5">
          <h3 class="font-bold text-white text-sm flex items-center gap-2">
            <span>⚡</span> SF Camper Reservation Strategy
          </h3>
          <ul class="space-y-1.5 text-slate-400 leading-normal">
            <li><strong class="text-emerald-400">ReserveCalifornia:</strong> 6 months rolling at <strong>8:00:00 AM PT sharp</strong>. Sync clocks; Steep Ravine, Bodega Wright's Beach, and Big Sur book in seconds.</li>
            <li><strong class="text-sky-400">Recreation.gov:</strong> National Parks & USFS drop at <strong>7:00:00 AM PT</strong>. Kirby Cove & Point Reyes backcountry drop 3 months rolling. Yosemite drops 15th of the month.</li>
            <li><strong class="text-amber-400">FCFS Tactics:</strong> For Mt. Tamalpais (Pantoll/Bootjack) arrive by 8:00 AM on Thursday or Friday morning. Bring exact cash or pay card at kiosk.</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Comprehensive Filterable Directory Table -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h2 class="text-xl font-bold text-white">Full Campground Intelligence Directory</h2>
          <p class="text-xs text-slate-400">Sort and inspect all 43 mapped destinations ordered from closest to furthest from Grace Cathedral.</p>
        </div>
        <div class="text-xs text-slate-400">
          Showing <span id="table-count" class="font-bold text-white">43</span> locations
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/40">
              <th class="py-3 px-3">Campground</th>
              <th class="py-3 px-3">Region</th>
              <th class="py-3 px-3">Agency</th>
              <th class="py-3 px-3">Drive (From Grace)</th>
              <th class="py-3 px-3">Reservation Rule</th>
              <th class="py-3 px-3">Sites</th>
              <th class="py-3 px-3">Composite Score</th>
              <th class="py-3 px-3">Key Hikes & Attractions</th>
              <th class="py-3 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody id="directory-tbody" class="divide-y divide-slate-800/60 text-slate-300">
            <!-- Dynamic rows populated via JS -->
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <!-- Client-Side Logic -->
  <script>
    const campgrounds = {campgrounds_json_str};
    const homePoint = {home_json_str};

    let selectedId = campgrounds[0].id;
    let filteredList = [...campgrounds];

    function getAgencyColor(agency) {{
      if (agency.includes("National Park") || agency.includes("NPS")) return "#38bdf8"; // sky blue
      if (agency.includes("State Park")) return "#34d399"; // emerald
      if (agency.includes("Forest") || agency.includes("BLM")) return "#fbbf24"; // amber
      return "#c084fc"; // purple for regional
    }}

    function renderMarkers() {{
      const container = document.getElementById("campground-markers");
      container.innerHTML = "";

      filteredList.forEach(cg => {{
        const color = getAgencyColor(cg.agency);
        const isSelected = cg.id === selectedId;

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", `cg-marker ${{isSelected ? 'active-marker' : ''}}`);
        g.setAttribute("transform", `translate(${{cg.svg_x}}, ${{cg.svg_y}})`);
        g.onclick = () => selectCampground(cg.id);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("r", isSelected ? "8" : "6");
        circle.setAttribute("fill", color);
        circle.setAttribute("stroke", isSelected ? "#ffffff" : "#0f172a");
        circle.setAttribute("stroke-width", "1.5");

        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = `${{cg.name}} (${{cg.drive_time_from_grace}}, ${{cg.distance_road_miles}} mi) - ${{cg.reservation_type}}`;

        g.appendChild(circle);
        g.appendChild(title);
        container.appendChild(g);
      }});
    }}

    function selectCampground(id) {{
      selectedId = id;
      const cg = campgrounds.find(c => c.id === id);
      if (!cg) return;

      // Update Card
      document.getElementById("card-region").textContent = cg.region;
      document.getElementById("card-title").textContent = cg.name;
      document.getElementById("card-agency").textContent = cg.agency;
      document.getElementById("card-score").textContent = cg.composite_score_out_of_10.toFixed(1);
      document.getElementById("card-drive").textContent = `${{cg.drive_time_from_grace}} (~${{cg.distance_road_miles}} mi)`;
      document.getElementById("card-capacity").textContent = `${{cg.num_sites}} sites (${{cg.site_types}})`;
      document.getElementById("card-rule-title").textContent = cg.reservation_type;
      document.getElementById("card-window").textContent = cg.reservation_window;
      document.getElementById("card-fee").textContent = cg.nightly_fee;
      document.getElementById("card-hikes").textContent = cg.nearby_hikes_attractions;
      document.getElementById("card-desc").textContent = cg.description;

      // Update links
      const mapsQuery = encodeURIComponent(`${{cg.name}}, California`);
      document.getElementById("card-google-maps").href = `https://www.google.com/maps/search/?api=1&query=${{mapsQuery}}`;
      
      let bookingUrl = "https://www.reservecalifornia.com/";
      if (cg.agency.includes("National Park") || cg.agency.includes("Forest") || cg.agency.includes("US Army")) {{
        bookingUrl = `https://www.recreation.gov/search?q=${{encodeURIComponent(cg.name)}}`;
      }} else if (cg.agency.includes("East Bay")) {{
        bookingUrl = "https://www.ebparks.org/recreation/camping";
      }} else if (cg.agency.includes("San Mateo")) {{
        bookingUrl = "https://www.smcgov.org/parks/reservations";
      }}
      document.getElementById("card-booking-link").href = bookingUrl;

      renderMarkers();
    }}

    function renderTable() {{
      const tbody = document.getElementById("directory-tbody");
      tbody.innerHTML = "";
      document.getElementById("table-count").textContent = filteredList.length;

      filteredList.forEach(cg => {{
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-800/40 transition cursor-pointer";
        tr.onclick = () => {{
          selectCampground(cg.id);
          window.scrollTo({{ top: 120, behavior: "smooth" }});
        }};

        tr.innerHTML = `
          <td class="py-3 px-3 font-semibold text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full inline-block" style="background-color: ${{getAgencyColor(cg.agency)}}"></span>
            ${{cg.name}}
          </td>
          <td class="py-3 px-3 text-slate-400">${{cg.region}}</td>
          <td class="py-3 px-3 text-slate-400">${{cg.agency}}</td>
          <td class="py-3 px-3 font-medium text-slate-200">${{cg.drive_time_from_grace}} <span class="text-slate-500">(${{cg.distance_road_miles}} mi)</span></td>
          <td class="py-3 px-3">
            <span class="px-2 py-0.5 rounded text-[11px] font-medium ${{
              cg.reservation_type.includes('Paid') ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20' :
              cg.reservation_type.includes('First-Come') ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
              'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            }}">
              ${{cg.reservation_type}}
            </span>
          </td>
          <td class="py-3 px-3 text-slate-300 font-semibold">${{cg.num_sites}}</td>
          <td class="py-3 px-3 font-bold text-emerald-400">${{cg.composite_score_out_of_10.toFixed(1)}}</td>
          <td class="py-3 px-3 text-slate-400 max-w-xs truncate" title="${{cg.nearby_hikes_attractions}}">${{cg.nearby_hikes_attractions}}</td>
          <td class="py-3 px-3 text-right">
            <button class="bg-slate-800 hover:bg-slate-700 text-sky-400 px-2 py-1 rounded text-[11px] font-medium">Inspect</button>
          </td>
        `;
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
          cg.description.toLowerCase().includes(query);

        const matchesRegion = (region === "ALL") || (cg.region === region);
        
        let matchesRule = true;
        if (rule === "Paid Reservation") matchesRule = cg.reservation_type.includes("Paid");
        if (rule === "First-Come") matchesRule = cg.reservation_type.includes("First-Come");
        if (rule === "Dispersed") matchesRule = cg.reservation_type.includes("Dispersed") || cg.nightly_fee.includes("$0") || cg.nightly_fee.toLowerCase().includes("free");

        let matchesAgency = true;
        if (agency === "National Park Service") matchesAgency = cg.agency.includes("National Park") || cg.agency.includes("NPS");
        if (agency === "California State Parks") matchesAgency = cg.agency.includes("California State Parks");
        if (agency === "US Forest Service") matchesAgency = cg.agency.includes("Forest") || cg.agency.includes("BLM");
        if (agency === "Regional") matchesAgency = cg.agency.includes("Regional") || cg.agency.includes("County");

        return matchesQuery && matchesRegion && matchesRule && matchesAgency;
      }});

      renderMarkers();
      renderTable();
    }}

    // Initial setup
    selectCampground(selectedId);
    renderMarkers();
    renderTable();
  </script>
</body>
</html>
"""

with open("campground_map_dashboard.html", "w") as f:
    f.write(html_template)

# Also write to artifact path so the user can easily view it in the side pane or browser
artifact_path = "/Users/bhimes/.gemini/antigravity/brain/4f5e62ae-22bd-4f6a-b221-6f4ac1a8ce8e/campground_explorer.html"
with open(artifact_path, "w") as f:
    f.write(html_template)

print("Saved campground_map_dashboard.html in workspace and artifact directory!")
