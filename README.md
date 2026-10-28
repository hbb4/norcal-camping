# NorCal Camping Intelligence & Cartographic Guide 🏕️🌲

An outdoor planning repository and interactive toolkit for exploring, planning, and booking campgrounds across Northern and Central California, anchored from San Francisco (Grace Cathedral).

---

## 🌟 Key Features

- **Interactive Map Dashboard (`campground_map_dashboard.html`)**  
  Filterable Leaflet web map featuring driving time calculations, regional boundaries, amenity badges, booking portals, and direct reservation links.
- **Cartographic Vector Map (`norcal_campground_map.svg`)**  
  A standalone regional SVG map plotting major camping hubs across the Bay Area, North Coast, Shasta-Cascade, Sierra Nevada, and Monterey / Big Sur.
- **Campground Intelligence Guide (`CAMPGROUND_INTELLIGENCE_GUIDE.md`)**  
  Field-tested reservation playbooks, booking window deadlines (ReserveCalifornia 8 AM PT rolling 6 months vs Recreation.gov 7 AM PT), FCFS arrival tactics, cancellation hunting workflows, and microclimate guidance.
- **Structured Campground Dataset (`campgrounds_data.json`)**  
  Comprehensive JSON database covering NPS, CA State Parks, USFS, BLM, and regional parks with precise GPS coordinates, site counts, elevation, and direct links.
- **Automated Data & Map Generation Pipeline**  
  Python automation scripts to build, validate, and render all guide assets from the master dataset.

---

## 📂 Repository Structure

```text
├── CAMPGROUND_INTELLIGENCE_GUIDE.md  # Comprehensive campground guide & reservation strategies
├── campground_map_dashboard.html     # Interactive Leaflet web dashboard
├── campgrounds_data.json             # Master campground JSON database
├── norcal_campground_map.svg         # Standalone SVG regional map
├── build_campgrounds_data.py         # Script to compile & validate campgrounds dataset
├── generate_map_dashboard.py         # Script to generate HTML dashboard
├── generate_svg_map.py               # Script to generate SVG map
├── generate_guide_markdown.py        # Script to render Markdown intelligence guide
├── AGENTS.md                         # Project workspace instructions
├── SOUL.md                           # Guide directives and principles
└── README.md                         # Project documentation
```

---

## 🚀 Quickstart

### 1. View the Interactive Dashboard
You can open `campground_map_dashboard.html` directly in your browser or run a quick local HTTP server:

```bash
python3 -m http.server 8000
```

Then visit [http://localhost:8000/campground_map_dashboard.html](http://localhost:8000/campground_map_dashboard.html).

### 2. Regenerate Assets
If you update `campgrounds_data.json` or `build_campgrounds_data.py`:

```bash
# Rebuild JSON database
python3 build_campgrounds_data.py

# Rebuild HTML dashboard
python3 generate_map_dashboard.py

# Rebuild SVG map
python3 generate_svg_map.py

# Rebuild Markdown guide
python3 generate_guide_markdown.py
```

---

## 🗺️ Covered Regions

- **San Francisco Bay & Coast**: Marin Headlands, Mount Tamalpais, Point Reyes National Seashore, Samuel P. Taylor, Half Moon Bay, Angel Island.
- **Santa Cruz Mountains & Central Coast**: Big Basin Redwoods, Portola Redwoods, Butano, Henry Cowell, New Brighton, Sunset State Beach.
- **Monterey Bay & Big Sur**: Pfeiffer Big Sur, Kirk Creek, Plaskett Creek, Andrew Molera, Limekiln, Julia Pfeiffer Burns.
- **Sonoma & Napa Wine Country / Coast**: Sonoma Coast, Salt Point, Sugarloaf Ridge, Bothe-Napa Valley.
- **North Coast & Redwoods**: Mendocino Headlands, Russian Gulch, Van Damme, Hendy Woods, Humboldt Redwoods, Prairie Creek Redwoods, Jedediah Smith.
- **Sierra Nevada & Lake Tahoe**: Emerald Bay, D.L. Bliss, Sugar Pine Point, Donner Memorial, Calaveras Big Trees, Yosemite Valley, Tuolumne Meadows.
- **Shasta-Cascade & Trinity**: Lassen Volcanic (Manzanita Lake, Summit Lake), Castle Crags, McArthur-Burney Falls, Trinity Alps.

---

## 📄 License

MIT or public domain for all data compilation and generation code. Campground names, park rules, and jurisdictions are property of their respective managing agencies (NPS, California State Parks, USFS, BLM).
