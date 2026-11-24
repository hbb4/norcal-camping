# Sierra Snow: Palisades Tahoe and Alpine Meadows

Snow forecast, observation and road-condition dashboard for Palisades Tahoe (Olympic Valley) and Alpine Meadows. Python standard library only; no `pip install`.

## What it shows

- **Forecast** from named models: HRRR 3 km (0–48 h) then GFS (primary), compared with NBM, GFS, ECMWF IFS, ICON, GEM, NWS gridded snowfall, and ~120 ensemble members (GEFS, ECMWF ENS, ICON-EPS). Each base/mid/summit tier is queried at its own coordinates.
- **Snowfall** = model liquid × snow fraction (from the wet-bulb zero height) × snow/liquid ratio (Cobb-style habit × lift, wind and near-freezing adjusted). Kuchera, 10:1 and the API's 7:1 field are shown for comparison.
- **Uncertainty**: 10th–90th percentile ranges from the ensembles; 7-day fan chart.
- **Atmospheric profile**: DGZ height and pressure, ice saturation and lift; precipitation type by elevation with dry bulb, wet bulb and dew-point depression per tier; skew-T log-P (model at any hour, or the latest Reno/Oakland radiosonde); ice-crystal habit diagram.
- **Observations**: CDEC snow pillows SQV (8,200 ft) and WC3 (6,750 ft), radiosondes, NWS Reno discussion and alerts.
- **Verification**: every forecast is archived and compared with the snow sensors once its 48 h window has passed.
- **Roads**: Caltrans chain controls on routed road geometry, with Interstate/US/California shields.
- **Settings**: °F/°C, in/cm, home resort, snowfall alert threshold.

See [DATA_SOURCES_AND_METHODOLOGY.md](DATA_SOURCES_AND_METHODOLOGY.md) for every formula, threshold and endpoint.

---

## 📂 Architecture & Directory Structure

```text
ski_resort_snow/
├── README.md                      # System overview and quickstart guide
├── DATA_SOURCES_AND_METHODOLOGY.md # Comprehensive data source & mathematical methodology documentation
├── dashboard.html                 # Modern, responsive dark-theme web dashboard (Leaflet + SVG)
├── update_snow_data.py            # CLI script to fetch all sources & compile data/live_snow_data.json
├── server.py                      # Server: refreshes data on launch, every 30 min (roads 5 min), /api/status
├── config/
│   ├── resorts.json               # GPS coordinates, elevation bands, CDEC station IDs, NWS grid coords
│   ├── sources.json               # Data provider definitions, weights, and alert thresholds
│   └── roads.json                 # Highway segment coordinates, checkpoints, passes, and polylines
├── collectors/
│   ├── __init__.py
│   ├── open_meteo_client.py       # Named models, sounding, SLR methods, ensembles, model comparison
│   ├── raob_client.py             # Observed radiosondes (REV, OAK) from IEM
│   ├── verification.py            # Forecast archive and verification against CDEC sensors
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
python3 server.py --open
```

`--open` launches your browser at the dashboard. Use `--port 8081` if 8080 is taken. Then visit:
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
