# Sierra Crest Ski Resort Snow Intelligence & Highway Operations 🎿❄️🚗

An interactive, multi-source snow forecast, telemetry reality-check, and highway operations dashboard built specifically for **Palisades Tahoe (Olympic Valley)** and **Alpine Meadows**, anchored along the Sierra Crest in Lake Tahoe, California.

---

## 🌟 Key Capabilities

1. **Multi-Source Reality-Check & Benchmarking**:
   - **Resort Operations & Snow Stakes**: Official 24h, 48h, 7-day snow stakes, season total, base depths, open lifts/trails counts, and surface condition notes.
   - **Open-Meteo High-Resolution Ensemble**: Multi-model numeric weather predictions (ECMWF IFS 9km, GFS 13km, and HRRR 3km) queried at both Base (6,200') and Summit (9,050') elevations.
   - **NOAA / National Weather Service (NWS Reno REV)**: Quantitative Precipitation Forecasts (QPF), quantitative snowfall amount grids (`snowfallAmount`), synoptic meteorologist discussions, and active Winter Storm Warnings.
   - **CDEC & USDA SNOTEL Automated Sensors**: Real-time ground truth telemetry from automated high-elevation stations (**SQV** Gold Coast at 8,010' and **WC3** Ward Creek #3 at 6,750') measuring ultrasonic snow depth, snow pillow Snow Water Equivalent (SWE), air temperature, and real snow density (Snow-to-Liquid Ratio).
   - **Caltrans Highway Operations (CWWP2)**: Live traction requirements (R-0, R-1, R-2, R-3) and mountain pass closures across I-80 Donner Pass, SR-89, SR-267, SR-28, and US-50 Echo Summit.

2. **Interactive Highway Map & Chain Controls (Leaflet Engine)**:
   - Visualizes live travel restrictions on an interactive dark-themed map centered on Lake Tahoe and Donner Pass.
   - Color-coded polylines for all major trans-Sierra highways and resort access spurs (Emerald Green R-0, Amber R-1, Vivid Orange R-2, Bright Red R-3, and Dashed Red for Closed passes).
   - Interactive popups displaying checkpoints, pass elevations, and official Caltrans advisories.
   - Interactive synchronization between route cards and map zoom.

3. **Stacked 48-Hour Forecast Chart (Base / Mid / Summit toggle)**:
   - Accumulated snow with a labelled inch scale, plus the other tiers and the raw-model total for comparison.
   - Hourly snowfall rate, a snow/mix/rain strip shaded by chance of precipitation, and wind and gusts at the selected elevation.
   - Time-height panel: dendritic growth zone (DGZ), snow level (from the wet-bulb zero height), freezing level, and tier elevations.
   - Snowfall is computed from the model sounding (liquid × snow fraction × Kuchera SLR). See methodology §3.2b.

4. **Elevation Gradient Modeling (Base vs. Summit)**:
   - Tracks the dynamic Sierra rain-snow line (freezing level / $0^\circ\text{C}$ isotherm).
   - Computes elevation accumulation spread:
     - **Olympic Valley**: 6,200' Base vs. 9,050' Summit (KT-22 / Granite Chief / Sibir).
     - **Alpine Meadows**: 6,835' Base (635' higher base!) vs. 8,637' Ward Peak.

5. **Consensus Forecast & Storm Intelligence**:
   - Calculates weighted consensus ranges for Next 24h, Next 48h, and 7-day storm totals.
   - **Powder Day Score (1–10)**: Balances fresh snow volume against high-wind hold penalties.
   - **Wind Hold Risk Index**: Flags gale-force crest gusts that impact exposed lifts: KT-22 Express, Summit 6, Aerial Tram, Funitel, and the Base to Base Gondola.

6. **Zero-Dependency Python Backend**:
   - Built entirely with Python's standard library (`urllib.request`, `json`, `html.parser`, `http.server`).
   - Requires zero `pip install` commands out of the box.

---

## 📂 Architecture & Directory Structure

```text
ski_resort_snow/
├── README.md                      # System overview and quickstart guide
├── DATA_SOURCES_AND_METHODOLOGY.md # Comprehensive data source & mathematical methodology documentation
├── dashboard.html                 # Modern, responsive dark-theme web dashboard (Leaflet + SVG)
├── update_snow_data.py            # CLI script to fetch all sources & compile data/live_snow_data.json
├── server.py                      # Lightweight HTTP & live API server (port 8080)
├── config/
│   ├── resorts.json               # GPS coordinates, elevation bands, CDEC station IDs, NWS grid coords
│   ├── sources.json               # Data provider definitions, weights, and alert thresholds
│   └── roads.json                 # Highway segment coordinates, checkpoints, passes, and polylines
├── collectors/
│   ├── __init__.py
│   ├── open_meteo_client.py       # High-res multi-model snowfall, freezing level, and wind gusts
│   ├── nws_client.py              # NOAA/NWS API client (snow grids, alerts, period forecasts)
│   ├── cdec_snotel_client.py      # Real-time CDEC/SNOTEL telemetry (SQV 8,010' & WC3 6,750')
│   ├── resort_scraper.py          # Official resort mountain report parser (snow stake & lift ops)
│   ├── caltrans_client.py         # Caltrans CWWP2 District 3 & 10 chain controls & pass closures
│   └── aggregator.py              # Cross-source reconciliation, consensus forecast, & storm scores
├── data/
│   ├── live_snow_data.json        # Unified output dataset containing live telemetry & forecasts
│   └── mock_live_data.py          # Realistic Sierra storm telemetry generator for offline / fallback
├── static/
│   ├── css/
│   │   └── dashboard.css          # Mountain glassmorphic UI stylesheet
│   └── js/
│       └── app.js                 # Interactive SVG chart, Leaflet map, tabs, & live refresh
└── tests/
    └── test_snow_pipeline.py      # Unit test suite
```

---

## 🚀 Quickstart

### 1. View the Interactive Dashboard

You can view `dashboard.html` immediately in two ways:

#### Option A: Run the Local Python Server (Recommended)
This enables the live `/api/refresh` button and REST API:

```bash
cd /Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow
python3 server.py
```

Then visit:
- **Dashboard UI**: [http://localhost:8080/](http://localhost:8080/)
- **Live Snow API**: [http://localhost:8080/api/snow](http://localhost:8080/api/snow)
- **Caltrans Road API**: [http://localhost:8080/api/roads](http://localhost:8080/api/roads)
- **Active Resorts API**: [http://localhost:8080/api/resorts](http://localhost:8080/api/resorts)

#### Option B: Open `dashboard.html` Directly
`dashboard.html` has pre-embedded telemetry and can be opened directly in any browser:

```bash
open /Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow/dashboard.html
```

---

### 2. Ingest Fresh Live Snow & Highway Data

To run the multi-source ingestion pipeline:

```bash
python3 update_snow_data.py
```

This will:
1. Query Open-Meteo, NOAA/NWS Reno, CDEC sensors (`SQV`, `WC3`), resort reports, and Caltrans CWWP2.
2. Calculate consensus forecast ranges, elevation spreads, powder scores, wind-hold alerts, and road restrictions.
3. Save the consolidated JSON to `data/live_snow_data.json`.
4. Automatically update the embedded data in `dashboard.html`.
5. Output a terminal summary report.

#### Offline / Simulation Mode:
```bash
python3 update_snow_data.py --mock
```

---

### 3. Run Unit Tests
```bash
python3 -m unittest discover -s tests
```

---

## 📖 In-Depth Technical Documentation

For the complete technical breakdown of endpoints, API parameters, formulas, and visual rendering mechanics, refer to:
👉 [**DATA_SOURCES_AND_METHODOLOGY.md**](file:///Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow/DATA_SOURCES_AND_METHODOLOGY.md)
