# Sierra Snow: Palisades Tahoe and Alpine Meadows

Snow forecast, observation and road-condition dashboard for Palisades Tahoe (Olympic Valley) and Alpine Meadows. Python standard library only; no `pip install`.

## What it shows

- **Forecast**, 7 days, from one selectable model at a time: NBM (default, read natively from NOAA including its own snowfall, snow/liquid ratio and snow level), four blends (Equal blend: equal-weight mean of the six single models; Skill blend (beta): weighted by hindcast skill; Short-range blend: NBM and HRRR/GFS as major members; ECMWF pair: HRES + AIFS), each with the members' range; members and weights in `config/sources.json`, ECMWF HRES, ECMWF AIFS, HRRR/GFS, ICON, UKMO, GEM. NBM's 2.5 km cells are moved to each tier's elevation using NBM's own hourly relationship with terrain around the resort. NWS gridded snowfall is adjusted the same way and shown beside the model at each tier, never blended. ~120 ensemble members (GEFS, ECMWF ENS, ICON-EPS) give the distributions. Each base/mid/summit tier is queried at its own coordinates.
- **Snowfall**: NBM's own snowfall field (elevation-adjusted). For the Open-Meteo models: liquid × snow fraction (from the wet-bulb zero height) × snow/liquid ratio (Cobb-style habit × lift, unadjusted); an experimental wind/near-freezing adjustment, Kuchera, 10:1 and the API's 7:1 field are shown for comparison. Calibration plan: [TUNING_PLAN.md](TUNING_PLAN.md).
- **Now**: a station observations section (right after the overview) lists the resort's base, mid and summit weather stations beside the selected model's first hour, both its 2 m value and the model column's free-air temperature at each station's height. At hour 0 the scene, phase panel and pills also use the station readings (footnoted).
- **Elevation time series**: temperature (2 m and free air), RH and visibility at base, mid and summit.
- **Uncertainty**: 10th–90th percentile ranges from the ensembles; 7-day fan chart.
- **Atmospheric profile**: DGZ height and pressure, ice saturation and lift; precipitation type by elevation with dry bulb, wet bulb and dew-point depression per tier; supercooled liquid water above the summit from HRRR (to 48 h) or RRFS (to 84 h) native output on AWS, with a switch between them (cloud and rain water colder than 0 °C by hour and pressure level, with the 0/−10/−20 °C isotherms, the DGZ, riming layers where snow or graupel shares the layer, and the column total); skew-T log-P (model at any hour, or the latest Reno radiosonde; HRRR/GFS column when NBM is selected); ice-crystal habit diagram with temperature × supersaturation regions and the base, mid and summit points. A second time slider in this section moves with the one in the hero.
- **Observations**: CDEC snow pillows SQV (8,010 ft, NRCS location) and WC3 (6,750 ft), radiosondes, NWS Reno discussion and alerts.
- **Verification**: every forecast is archived and compared with the snow sensors once its 48 h window has passed.
- **Roads**: Caltrans chain controls on routed road geometry, with Interstate, U.S. Route and California State Route shields drawn to the real sign designs.
- **Lifts**: the lifts you care about first (configured order in `config/resorts.json` → `priority_lifts`), the rest behind an expander.
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
├── cssl_sync.py                   # Snow Lab calibration data: season log + Dryad archive import (cron: scripts/cssl_cron.sh)
├── nrcs_sync.py                   # SNOTEL hourly snow water, depth, precipitation, temperature (7 sites, WY2021 on)
├── nbm_archive_sync.py            # Past NBM forecasts (AWS archive) for SNOTEL storm-days
├── station_bias.py                # Resort stations vs model 2 m and free-air temperature, per tier
├── blend_weights.py               # Skill weights for the blends (live archive, or --hindcast from Open-Meteo's archive)
├── calibration_baseline.py        # NBM raw vs elevation-adjusted scores at the SNOTEL sites on storm-days
├── skill_report.py                # Member and blend skill at the pillows: days, whole storms, bias-corrected, categorical
├── neighborhood_hindcast.py       # Cells around each pillow: elevation-shift test, and `fit --apply` for the Elevation-adjusted blend
├── server.py                      # Server: refreshes data on launch, every 30 min (roads 5 min), /api/status
├── config/
│   ├── resorts.json               # GPS coordinates, elevation bands, CDEC station IDs, NWS grid coords
│   ├── sources.json               # Data provider definitions, weights, and alert thresholds
│   └── roads.json                 # Highway segment coordinates, checkpoints, passes, and polylines
├── collectors/
│   ├── __init__.py
│   ├── open_meteo_client.py       # Named models, sounding, SLR methods, ensembles, model comparison
│   ├── nbm_client.py              # NOAA NBM from NOMADS (grid box around the resorts)
│   ├── grib2_simple.py            # Pure-Python GRIB2 reader (Lambert grid, simple packing)
│   ├── grib2_complex.py           # GRIB2 complex packing + spatial differencing (NBM archive files, HRRR point values)
│   ├── nbm_archive.py             # NBM archive on AWS: index, byte ranges, extended box
│   ├── hrrr_slw.py                # HRRR and RRFS on AWS: supercooled liquid, riming layers and column total at the summits
│   ├── storm_days.py              # Storm-days from SNOTEL hourly data (QC rules applied)
│   ├── nbm_downscale.py           # Moves NBM/NWS cell values to tier elevations (local regression)
│   ├── precip_shift.py            # Precipitation elevation shift from a model's own neighborhood (Elevation-adjusted blend)
│   ├── grid_terrain.py            # 2.5 km cell terrain heights from the NWS grid (cached)
│   ├── raob_client.py             # Observed radiosonde (REV) from IEM
│   ├── verification.py            # Forecast archive and verification against CDEC sensors
│   ├── nws_client.py              # NOAA/NWS API client (snow grids, alerts, period forecasts)
│   ├── cdec_snotel_client.py      # Real-time CDEC/SNOTEL telemetry (SQV 8,010' & WC3 6,750')
│   ├── nrcs_client.py             # NRCS AWDB hourly SNOTEL history for calibration (flags kept)
│   ├── cssl_client.py             # Central Sierra Snow Lab season page + Dryad archive
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
1. Query Open-Meteo, NOAA/NWS Reno, CDEC sensors (`SQV`, `WC3`), resort reports, Caltrans CWWP2, and HRRR and RRFS on AWS (a new 00/06/12/18Z cycle is about 0.55 GB of byte-range downloads for HRRR and 1.2 GB for RRFS, 3–4 minutes of work in all, once per 6 hours; cached in `data/cache/`).
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

### 4. Calibration data (optional, for TUNING_PLAN.md)
```bash
python3 cssl_sync.py            # log this season from cssl.berkeley.edu, check the Dryad version
python3 cssl_sync.py import     # unpack the Dryad zip downloaded in the browser
```
Cron (three runs a day; the lab posts its 8 AM board by 9 AM PST):
```
30 9,13,18 * * * /bin/bash /Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow/scripts/cssl_cron.sh
```
SNOTEL hourly history (seven sites; AWDB keeps the full record, so no schedule is needed):
```bash
python3 nrcs_sync.py            # merge values added or edited since the last sync (backfills on first run)
python3 nrcs_sync.py status     # what is on disk
```
Past NBM forecasts for those storm-days (from the NOAA archive on AWS):
```bash
python3 nbm_archive_sync.py storm-days     # storm-days from the SNOTEL data
python3 nbm_archive_sync.py fetch          # day-1 forecasts for every confirmed storm-day (~6.7 GB, resumable)
python3 nbm_archive_sync.py terrain        # cell heights for the extended box (once)
python3 nbm_archive_sync.py status
```
Station-vs-model temperature errors and the 2 m/free-air coupling weight per tier (grows with every pipeline run):
```bash
python3 station_bias.py
```
Skill weights for the blends (needs ~15 cold, wet days in the per-model archive, which every run adds to; `--hindcast` fits now from Open-Meteo's archived forecasts):
```bash
python3 nrcs_sync.py && python3 blend_weights.py
python3 blend_weights.py --hindcast --write
```
Baseline scores for NBM at the SNOTEL sites (after `nbm_archive_sync.py fetch`):
```bash
python3 calibration_baseline.py --md
```
Precipitation correction for the Elevation-adjusted blend (elevation shift from each model's neighborhood, then a residual multiplier; the fetch is ~4,000 Open-Meteo calls for five seasons, the rest runs from the cache in seconds):
```bash
python3 neighborhood_hindcast.py fetch --plan
python3 neighborhood_hindcast.py score --md
python3 neighborhood_hindcast.py fit --apply
```
HRRR or RRFS supercooled liquid at both summits, hour by hour, without a full refresh (same cache as the server):
```bash
python3 collectors/hrrr_slw.py
python3 collectors/hrrr_slw.py --model rrfs
```

---

## 📖 In-Depth Technical Documentation

For the complete technical breakdown of endpoints, API parameters, formulas, and visual rendering mechanics, refer to:
👉 [**DATA_SOURCES_AND_METHODOLOGY.md**](file:///Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow/DATA_SOURCES_AND_METHODOLOGY.md)
