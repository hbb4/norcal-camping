# Sierra Crest Snow Intelligence: Data Sources & Technical Methodology 📡❄️🏔️

This document details the telemetry ingestion pipeline, meteorological formulas, data sources, API endpoints, and display generation logic powering the **Sierra Crest Snow Intelligence & Highway Operations Dashboard**.

---

## 📑 Table of Contents
1. [System Architecture & Ingestion Overview](#1-system-architecture--ingestion-overview)
2. [Data Sources Reference & Endpoint Specification](#2-data-sources-reference--endpoint-specification)
   - [A. Palisades Tahoe & Alpine Meadows Operations](#a-palisades-tahoe--alpine-meadows-operations)
   - [B. Open-Meteo High-Resolution Ensemble (ECMWF / GFS / HRRR)](#b-open-meteo-high-resolution-ensemble-ecmwf--gfs--hrrr)
   - [C. NOAA / National Weather Service Reno (REV)](#c-noaa--national-weather-service-reno-rev)
   - [D. California Data Exchange Center (CDEC) & USDA NRCS SNOTEL](#d-california-data-exchange-center-cdec--usda-nrcs-snotel)
   - [E. Caltrans CWWP2 Highway Chain Controls & Pass Closures](#e-caltrans-cwwp2-highway-chain-controls--pass-closures)
3. [Mathematical Formulas & Synthesis Logic](#3-mathematical-formulas--synthesis-logic)
   - [3.1 Consensus Snowfall Forecast (24h, 48h, 7-Day)](#31-consensus-snowfall-forecast-24h-48h-7-day)
   - [3.2 Elevation Gradient & Rain-Snow Line Analysis](#32-elevation-gradient--rain-snow-line-analysis)
   - [3.3 Snow-to-Liquid Ratio (SLR) & Snowpack Density](#33-snow-to-liquid-ratio-slr--snowpack-density)
   - [3.4 Powder Day Score (1–10 Scale)](#34-powder-day-score-110-scale)
   - [3.5 Wind Hold Risk Index](#35-wind-hold-risk-index)
   - [3.6 Caltrans Restriction Severity Hierarchy](#36-caltrans-restriction-severity-hierarchy)
4. [Frontend UI & Visualization Rendering Mechanics](#4-frontend-ui--visualization-rendering-mechanics)
   - [4.1 Stacked 48-Hour Forecast Chart](#41-stacked-48-hour-forecast-chart)
   - [4.2 Leaflet Interactive Highway Map & Route Polylines](#42-leaflet-interactive-highway-map--route-polylines)
   - [4.3 Multi-Source Reality-Check Benchmark Matrix](#43-multi-source-reality-check-benchmark-matrix)

---

## 1. System Architecture & Ingestion Overview

The system ingests, normalizes, and reconciles weather and road data across 5 distinct domains:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION SOURCES                          │
├─────────────────┬──────────────────┬─────────────────┬─────────────────┤
│ Resort Reports  │ Open-Meteo (3km) │  NOAA/NWS Reno  │ CDEC / SNOTEL   │
│ Operations Stake│ Numerical Models │  WFO REV Grids  │ SQV (8,010')    │
│ Lifts & Trails  │ Base vs. Summit  │  Storm Warnings │ WC3 (6,750')    │
└────────┬────────┴────────┬─────────┴────────┬────────┴────────┬────────┘
         │                 │                  │                 │
         └─────────────────┼──────────────────┼─────────────────┘
                           ▼                  ▼
┌──────────────────────────────────────────────────────┬─────────────────┐
│           SnowAggregator Engine                      │ Caltrans CWWP2  │
│  - Weighted Consensus Forecast Modeling              │ D03 & D10 Feeds │
│  - Elevation Gradient / Rain-Snow Differential       │ Chain Controls  │
│  - Dynamic SLR & Sierra Snow Quality Index           │ Pass Closures   │
│  - Ridge Wind Hold Standby Vulnerability             │ Road Polylines  │
└──────────────────────────┬───────────────────────────┴────────┬────────┘
                           ▼                                    ▼
             ┌───────────────────────────┐
             │   live_snow_data.json     │
             └─────────────┬─────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   DASHBOARD VISUALIZATION LAYER                        │
│  • KPI Hero Cards (Consensus 24h/48h, 7-Day Storm, Powder Score)       │
│  • Stacked 48h chart (accum / rate / ptype / wind / time-height)      │
│  • Caltrans Highway Operations Map (Leaflet.js + Colored Polylines)    │
│  • Elevation Gradient Breakdown (Base 6,200' vs Summit 9,050')         │
│  • Multi-Source Benchmark Matrix (Resort vs Models vs Ground Sensors)   │
│  • Lift Wind Hold Standby Matrix (KT-22, Summit 6, Gondola)            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Sources Reference & Endpoint Specification

### A. Palisades Tahoe & Alpine Meadows Operations
- **Provider**: Palisades Tahoe Operations & Ski Patrol
- **Scraper Module**: `collectors/resort_scraper.py`
- **Target URL**: `https://www.palisadestahoe.com/mountain-information/snow-and-weather-report`
- **Secondary URL**: `https://www.palisadestahoe.com/mountain-information/snowfall-tracker`
- **Cadence**: Refreshed every 30–60 minutes by resort mountain dispatch
- **Extracted Fields**:
  - `snow_24h_inches`: 24-hour official snow stake reading
  - `snow_48h_inches`: 48-hour cumulative snow stake reading
  - `snow_7d_inches`: 7-day storm cycle total
  - `season_total_inches`: Season cumulative snowfall
  - `base_depth_base_inches`: Settled snow depth at base area (Olympic Village 6,200' / Alpine Base 6,835')
  - `base_depth_summit_inches`: Settled snow depth at upper mountain stake (High Camp 8,200' / Ward Peak 8,637')
  - `lifts_open` / `lifts_total`: Open lifts ratio (e.g. 23 / 29 at Palisades, 9 / 13 at Alpine)
  - `trails_open` / `trails_total`: Open trails count
  - `surface_condition`: Grooming report ("Powder", "Machine Groomed", "Variable")
  - `operations_note`: Wind standby notices (e.g. Base to Base Gondola hold status)

### B. Open-Meteo High-Resolution Ensemble (ECMWF / GFS / HRRR)
- **Provider**: Open-Meteo Weather API
- **Client Module**: `collectors/open_meteo_client.py`
- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **HTTP Method**: `GET`
- **Authentication**: None required (public open meteorological API)
- **Query Parameters**:
  ```http
  GET /v1/forecast?latitude=39.1970&longitude=-120.2356&elevation=2758
      &hourly=snowfall,snow_depth,temperature_2m,precipitation_probability,precipitation,freezing_level_height,wind_speed_10m,wind_gusts_10m,weather_code
      &daily=snowfall_sum,precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,wind_gusts_10m_max
      &timezone=America%2FLos_Angeles&precipitation_unit=inch&wind_speed_unit=mph&temperature_unit=fahrenheit
  ```
- **Dual-Elevation Sampling Strategy**:
  - **Base Query**: Elevation set to `1,890m` (6,200 ft) for Palisades Valley floor / `2,083m` (6,835 ft) for Alpine base.
  - **Summit Query**: Elevation set to `2,758m` (9,050 ft) for Granite Chief / KT-22 / `2,633m` (8,637 ft) for Ward Peak.
- **Key Metrics Extracted**:
  - Hourly snowfall rate (`snowfall` in inches/hour)
  - Freezing level height (`freezing_level_height` in meters, converted to feet: $h_{\text{ft}} = h_{\text{m}} \times 3.28084$)
  - Sustained wind speed at 10m (`wind_speed_10m` in mph)
  - Peak wind gusts at 10m (`wind_gusts_10m` in mph)
  - Ambient air temperature at 2m (`temperature_2m` in °F)
  - Probability of precipitation (`precipitation_probability` %)

### C. NOAA / National Weather Service Reno (REV)
- **Provider**: NOAA / National Weather Service Weather Forecast Office Reno, NV (REV)
- **Client Module**: `collectors/nws_client.py`
- **Base URL**: `https://api.weather.gov`
- **HTTP Headers**: `User-Agent: SierraSnowDashboard/2.0 (outdoor-planning@example.com)`, `Accept: application/geo+json`
- **Endpoints**:
  1. **Points Metadata**: `https://api.weather.gov/points/39.1970,-120.2356` (Returns WFO `REV`, Grid X `41`, Grid Y `82`)
  2. **12-Hour Text Periods**: `https://api.weather.gov/gridpoints/REV/41,82/forecast` (Detailed synoptic forecast periods)
  3. **Quantitative Precipitation & Snow Grid**: `https://api.weather.gov/gridpoints/REV/41,82` (Quantitative `snowfallAmount` in millimeters, converted to inches)
  4. **Active Hazard Alerts**: `https://api.weather.gov/alerts/active?point=39.1970,-120.2356` (Winter Storm Warnings, Blizzard Warnings, High Wind Warnings, Avalanche Watches)

### D. California Data Exchange Center (CDEC) & USDA NRCS SNOTEL
- **Provider**: California Department of Water Resources (DWR) & USDA Natural Resources Conservation Service (NRCS)
- **Client Module**: `collectors/cdec_snotel_client.py`
- **Endpoint**: `https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet`
- **Query Parameters**:
  ```http
  GET /dynamicapp/req/JSONDataServlet?Stations=SQV,WC3&SensorNums=3,82,6&dur_code=H&Start=YYYY-MM-DD
  ```
- **Monitored Sensor Stations**:
  - **Station `SQV`**: Squaw Valley Gold Coast (Elevation: 8,010 ft | Placer County | Truckee River Basin)
  - **Station `WC3`**: Ward Creek #3 / Alpine Meadows Boundary (Elevation: 6,750 ft | Placer County | Lake Tahoe Basin)
- **Sensor Channel Definitions**:
  - **Sensor `3`**: Snow Water Content / SWE (Snow Water Equivalent) in inches (measured via stainless steel snow pillow sensor)
  - **Sensor `82`**: Snow Depth in inches (measured via ultrasonic distance sensor pointed down at ground stake)
  - **Sensor `6`**: Air Temperature in °F (shielded thermistor)

### E. Caltrans CWWP2 Highway Chain Controls & Pass Closures
- **Provider**: California Department of Transportation (Caltrans) Commercial Wholesale Web Portal 2
- **Client Module**: `collectors/caltrans_client.py`
- **Endpoints**:
  - **District 3 (Sacramento Valley & Sierra Passes)**: `https://cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json`
  - **District 10 (Central Sierra Passes)**: `https://cwwp2.dot.ca.gov/data/d10/cc/ccStatusD10.json`
- **Cadence**: Refreshed dynamically every 1 to 5 minutes by Caltrans dispatch
- **JSON Structure**:
  ```json
  {
    "cwwp2": {
      "data": {
        "district": 3,
        "dataType": "CC",
        "cc": [
          {
            "route": "80",
            "nearbyPlace": "Kingvale",
            "direction": "Eastbound",
            "elevation": 5800,
            "ccStatus": {
              "status": "R-2",
              "description": "Chains required on all vehicles except four-wheel/all-wheel drive with snow tires on all 4 wheels."
            }
          }
        ]
      }
    }
  }
  ```

---

## 3. Mathematical Formulas & Synthesis Logic

### 3.1 Consensus Snowfall Forecast (24h, 48h, 7-Day)
Discrepancies between commercial models and government forecasts are reconciled using a multi-source weighted ensemble:

$$\text{Expected}_{48\text{h}} = \left( \text{Open-Meteo Summit}_{48\text{h}} \times 0.55 \right) + \left( \text{NWS REV QPF}_{48\text{h}} \times 0.45 \right)$$

$$\text{Expected}_{24\text{h}} = \text{Expected}_{48\text{h}} \times 0.55$$

The uncertainty spread range is established as:
$$\text{Min} = \text{Expected} \times 0.72 \quad\quad \text{Max} = \text{Expected} \times 1.30$$

The 7-day storm total incorporates the multi-model extended accumulation:
$$\text{Total}_{7\text{d}} = \text{Open-Meteo}_{7\text{d}}$$

### 3.2 Elevation Gradient & Rain-Snow Line Analysis
Because Sierra atmospheric river events frequently possess high freezing levels, accumulation varies sharply across elevation:

$$\Delta_{\text{Spread}} = \max\left(0, \text{Summit}_{48\text{h}} - \text{Base}_{48\text{h}}\right)$$

- **Olympic Valley**: Base at 6,200', Mid at 8,010', Summit at 9,050'. Vertical drop: 2,850'.
- **Alpine Meadows**: Base at 6,835' (635' higher base!), Mid at 7,800', Summit at 8,637'.
- **Rain-Snow Line Risk Flagging**:
  - If $\max(\text{Freezing Level}) > 7,000'$, flag **HIGH RISK** (rain/slush at Olympic Village base).
  - If $6,200' < \max(\text{Freezing Level}) \le 7,000'$, flag **MODERATE RISK** (Alpine base stays cold snow, Olympic Valley base near transition line).
  - If $\max(\text{Freezing Level}) \le 6,200'$, flag **LOW RISK** (100% all-snow event throughout the entire vertical drop).

### 3.2b Sounding-Derived Snow Diagnostics (Open-Meteo pressure levels)
`collectors/open_meteo_client.py` makes one extra Open-Meteo call per resort for pressure-level data at 850, 800, 750, 700, 650, 600, 550, 500, 450 and 400 hPa: `temperature`, `relative_humidity`, `geopotential_height`, `vertical_velocity`, `wind_speed`, `wind_direction`. Each forecast hour then has a model sounding, and these values come from it:

| Diagnostic | How it's computed | Why it matters |
|---|---|---|
| **Wet-bulb zero height (WBZ)** | Stull (2011) wet-bulb at each level, then interpolate to where it crosses 0 °C | Falling snow cools the air it melts and evaporates into, so the snow line follows the wet-bulb 0 °C height, not the dry 0 °C freezing level |
| **Snow level** | WBZ − 500 ft | Flakes survive a few hundred feet below WBZ before turning to rain |
| **Snow fraction per tier** | 1 at or above WBZ, 0 at 1,000 ft below it, linear in between. Overridden to all-snow if surface wet bulb ≤ 31 °F and all-rain if ≥ 36 °F | Drives the snow / mix / rain split and the chance of snow vs. rain (PoP × fraction) |
| **Kuchera SLR** | `T_max` = warmest temperature between the tier and 500 hPa. If `T_max` > 271.16 K: SLR = 12 + 2·(271.16 − T_max), else SLR = 12 + (271.16 − T_max). Clamped to 4–25 | Open-Meteo's `snowfall` field uses a fixed ~7:1 ratio. Kuchera scales the ratio with column temperature (cold = fluffy, warm = dense) |
| **Snowfall** | liquid precip × snow fraction × Kuchera SLR | The primary number shown in the chart and KPIs. The raw 7:1 model value is kept as `model_snowfall_in_hr` and drawn dashed |
| **DGZ** | Heights where T = −12 °C (base) and −18 °C (top); mean RH and vertical motion sampled at bottom, middle and top | Dendrites grow fastest here. **Saturated (RH ≥ 85%) and rising (≥ 10 cm/s)** is the "crosshair" signature for efficient, high-ratio snowfall |
| **Surface mixing ratio** | 621.97·e/(p − e), with e from dew point and p from the standard atmosphere at the tier height | Low-level water vapour: how much liquid a storm can deliver. At ~800 hPa: ≥ 5 g/kg is AR-type moisture, 2.5–5 is a typical cold Pacific storm, < 2.5 is cold and dry |
| **Tier winds** | Summit: free-air wind interpolated from pressure levels to the summit height. Base: model 10 m wind (sheltered valley). Mid: 60% of the way from 10 m toward free-air. Gusts = wind × the model's 10 m gust factor (clamped to 1.15–1.4) | Open-Meteo's `elevation=` parameter adjusts temperature but **not** wind, so on its own every tier would get the same smoothed 10 m wind |

**Gotchas found while building this:**
- With `precipitation_unit=inch`, Open-Meteo returns `freezing_level_height` in **feet**. Earlier code converted it a second time.
- Open-Meteo's `vertical_velocity` uses the pressure-coordinate sign (**negative = rising**). The collector flips it so positive means ascent.
- The python.org macOS Python ships without CA certificates, so every HTTPS request failed and every source silently fell back to mock data. `collectors/http_ssl.py` now installs a urllib opener that uses certifi or the OS CA bundle.

### 3.3 Snow-to-Liquid Ratio (SLR) & Snowpack Density
Ground truth sensor density is computed by dividing real-time ultrasonic depth gain by snow pillow SWE gain over the preceding 24-hour window:

$$\text{SLR} = \frac{\Delta \text{Snow Depth}_{24\text{h}} \text{ (inches)}}{\Delta \text{SWE}_{24\text{h}} \text{ (inches)}}$$

Density is classified as:
- $\text{SLR} \ge 16.0$: **Cold Blower Powder** (Dry, ultra-light, low water density)
- $11.0 \le \text{SLR} < 16.0$: **Classic Sierra Cream** (Optimal packing, high flotation)
- $7.0 \le \text{SLR} < 11.0$: **Sierra Cement** (Dense, high-moisture maritime snowpack)
- $\text{SLR} < 7.0$: **Wet Slush / Rain on Snow** (Heavy moisture, deteriorating base)

### 3.4 Powder Day Score (1–10 Scale)
The Powder Day Score evaluates ride quality by balancing new snowfall against wind-hold penalties:

$$\text{Base Score} = \min\left(10.0, \, \text{Expected}_{24\text{h}} \times 0.55\right)$$

$$\text{Wind Penalty} = \begin{cases} 
1.2 & \text{if } \text{Peak Crest Gusts} > 60\text{ mph} \\
0.5 & \text{if } 45\text{ mph} < \text{Peak Crest Gusts} \le 60\text{ mph} \\
0.0 & \text{if } \text{Peak Crest Gusts} \le 45\text{ mph}
\end{cases}$$

$$\text{Powder Score} = \max\left(1.0, \, \min\left(10.0, \, \text{Base Score} - \text{Wind Penalty}\right)\right)$$

### 3.5 Wind Hold Risk Index
Evaluates ridge-top wind gust forecasts against physical lift mechanical operating limits:
- **$\ge 65\text{ mph}$ Peak Crest Gusts**: **HIGH RISK**. Upper mountain lifts (**KT-22 Express**, **Summit 6**, **Headwall Express**, **Granite Chief**) and the **Base to Base Gondola** placed on wind standby.
- **$45\text{ to }64\text{ mph}$ Peak Crest Gusts**: **MODERATE RISK**. Exposed ridgeline lifts encounter intermittent stoppages.
- **$< 45\text{ mph}$ Peak Crest Gusts**: **LOW RISK**. Normal scheduled mountain lift operations.

### 3.6 Caltrans Restriction Severity Hierarchy
When combining multiple checkpoints along a single mountain corridor, the aggregator reports the most restrictive level in effect:
$$\text{CLOSED} > \text{R-3} > \text{R-2} > \text{R-1} > \text{R-0}$$

---

## 4. Frontend UI & Visualization Rendering Mechanics

### 4.1 Stacked 48-Hour Forecast Chart
Rendered as plain SVG in `static/js/app.js` (`renderHourlyDualAxisChart`). The tier toggle switches between **Base / Mid / Summit**. Five panels share one time axis, and each has its own labelled scale (no dual axes):
1. **Accumulated snow (in)**: the selected tier is filled, the other tiers are drawn faint with end labels, and the Open-Meteo raw 7:1 total is dashed.
2. **Hourly snowfall (in/hr)**: SLR-adjusted. Bar opacity drops when part of the precipitation falls as rain.
3. **Precip type strip**: snow (sky blue) / mix (violet) / rain (green). Cell opacity is the chance of precipitation.
4. **Wind at the selected tier**: sustained wind as a line, gusts as bars coloured by lift-hold threshold (<45 / 45–64 / ≥65 mph), and direction arrows every 6 h.
5. **Time-height profile**: DGZ band (darker = wetter, hatched = saturated and rising), snow level, freezing level, and the base/mid/summit elevations.

Hovering anywhere shows a crosshair and a tooltip with precip type, chance of snow vs. rain, snowfall, liquid and SLR, temperature and wet bulb, wind and gusts, snow and freezing levels, DGZ layer with RH and lift, and mixing ratio.

### 4.2 Leaflet Interactive Highway Map & Route Polylines
- **Engine**: Leaflet.js 1.9.4 with Esri World Dark Gray Canvas + World Hillshade Dark tiles (no API key).
- **Geometry**: Each corridor's polyline is routed on the OpenStreetMap road network with OSRM (`router.project-osrm.org`), between the segment's original endpoints, and stored in `config/roads.json` (~300–3,300 points per route).
- **Labels**: route shields showing the live R-level, pass markers with elevation, resort and town labels, and an on-map R-level legend.
- **Live matching**: CWWP2 records (`data[].cc.location` / `statusData`) are matched to a segment when the route number matches and the checkpoint is within 2 km of the segment's line. The most restrictive status wins.
- **Center**: Lake Tahoe and Donner Pass (`[39.22, -120.2]`, zoom 10).
- **Corridor Polylines**:
  - **I-80 Donner Pass**: Sacramento → Colfax → Kingvale → Donner Summit (7,239') → Truckee → Reno.
  - **SR-89 North**: Tahoe City → Olympic Valley turnoff → Alpine Meadows turnoff → Truckee.
  - **SR-89 South (Emerald Bay)**: Tahoe City → Meeks Bay → Emerald Bay (6,920') → South Lake Tahoe.
  - **SR-267**: Truckee → Northstar → Brockway Summit (7,179') → Kings Beach.
  - **SR-28**: Tahoe City → Carnelian Bay → Kings Beach → Incline Village.
  - **US-50**: Placerville → Twin Bridges → Echo Summit (7,377') → Meyers → South Lake Tahoe.
  - **Resort Spurs**: Olympic Valley Road and Alpine Meadows Road.
- **Color Coding**:
  - `R-0`: `#10b981` (Emerald Green)
  - `R-1`: `#f59e0b` (Amber)
  - `R-2`: `#f97316` (Vivid Orange)
  - `R-3`: `#ef4444` (Bright Red)
  - `CLOSED`: `#e11d48` (Dashed Red with 6px stroke)
- **Interactive Sync**: Clicking any road card in the right-hand panel automatically centers and zooms the Leaflet map to that corridor and triggers its status popup.

### 4.3 Multi-Source Reality-Check Benchmark Matrix
The matrix evaluates four parallel perspectives across five critical operational metrics:
1. **Next 24h Snowfall**: Resort Operations stake vs Open-Meteo summit model vs NWS REV forecast vs CDEC 24h ultrasonic sensor delta.
2. **Next 48h Storm Total**: Cumulative stake vs 48h numerical model vs NWS quantitative precipitation vs CDEC SWE accumulation rate.
3. **Snowpack / Base Depth**: Resort base/summit stake claims vs ECMWF dynamic depth tracking vs CDEC automated snow pillow depth.
4. **Snow Density / Quality (SLR)**: Resort surface description vs Open-Meteo SLR model vs CDEC physical $\text{Depth}/\text{SWE}$ measured ratio.
5. **Ridge Winds & Lift Operations**: Resort operations wind notice vs Open-Meteo peak crest gusts vs NWS synoptic gale warnings vs CDEC air temperature sensor.

---

## 5. Local Execution & REST API Endpoints

When running `python3 server.py`, the following REST endpoints are active:
- `GET /` or `/dashboard.html`: Serves the primary interactive dashboard.
- `GET /api/snow`: Returns the complete consolidated JSON payload (metadata, resorts, road conditions).
- `GET /api/roads`: Returns the Caltrans road conditions and polyline segment geometry.
- `GET /api/resorts`: Returns the active resort configuration from `config/resorts.json`.
- `POST /api/refresh` or `GET /api/refresh`: Triggers an on-demand pass of the multi-source aggregation engine and returns updated telemetry.
