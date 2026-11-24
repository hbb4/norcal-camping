# Sierra Snow: Data Sources and Methodology

How every number on the dashboard is produced. Code references are to `collectors/`.

## 1. Refresh cycle

`python3 server.py` starts a full refresh immediately on launch, then:

| Job | Interval | Contents |
|---|---|---|
| Full refresh | 30 min | models, ensembles, model sounding, NWS, CDEC sensors, radiosondes, Caltrans, verification |
| Roads | 5 min | Caltrans CWWP2 only |
| Manual | Refresh button / `R` key | full refresh (`POST /api/refresh`) |

The page polls `GET /api/status` (every 1.5 s while a refresh runs, every 30 s otherwise), shows per-step progress, and reloads the dataset when a newer one is written. Every source carries `fetched_at_utc`.

**Failures never fall back to mock data.** If a source fails, the previous successful data for that source is kept and marked `stale`, with its original fetch time and the error; if there is none it is `error`. Mock data is only produced by `update_snow_data.py --mock`.

## 2. Sources

### 2.1 Numerical models (via Open-Meteo, `open_meteo_client.py`)

| Role | Model | Provider | Grid | Notes |
|---|---|---|---|---|
| **Primary** | `gfs_seamless` | NOAA/NCEP | HRRR 3 km for ~0–47 h, then GFS 0.25° | Surface fields at each tier; full sounding at the summit |
| Comparison | HRRR | NOAA/NCEP | 3 km | Current run length shown (often 43–48 h) |
| Comparison | NBM | NOAA/NWS | 2.5 km | Statistically post-processed blend; surface only |
| Comparison | GFS (`gfs_global`) | NOAA/NCEP | 13–25 km | |
| Comparison | ECMWF IFS | ECMWF | 0.25° | |
| Comparison | ICON | DWD | 13 km (global over the US) | |
| Comparison | GEM | ECCC | 10–15 km | Open-Meteo's run metadata for GEM is stale, so no run time is shown |
| Ensembles | GEFS, ECMWF ENS, ICON-EPS | NOAA, ECMWF, DWD | 0.25° class | ~120 members, precipitation at each tier |

Run times come from `https://api.open-meteo.com/data/{model}/static/meta.json` (`last_run_initialisation_time`, `last_run_availability_time`). Earlier versions requested Open-Meteo's unnamed `best_match` blend; that is no longer used.

**Units gotcha:** with `precipitation_unit=inch`, Open-Meteo returns all lengths in feet, including `freezing_level_height` and `geopotential_height`. Surface queries use inches/feet; the sounding query does not set it, so heights are meters.

### 2.2 NWS (`nws_client.py`)

The Sierra crest is the boundary between NWS Reno (REV) and NWS Sacramento (STO). The base points of both resorts are in REV; both summit points fall in STO's grid.

- Alerts and the Area Forecast Discussion (Key Messages / Synopsis section) come from the office covering the **base** point (REV).
- Gridded snowfall (`snowfallAmount`, mm per interval) is summed over the next 24 h, 48 h and the full grid, both at the **summit** cell (STO, ~7,700 ft mean cell elevation) and the **base** cell (REV, ~6,300 ft). The summit cell is used in the 24/48 h blend.
- Grid cells are resolved from coordinates at run time (`/points/{lat},{lon}`); the configured grid in older versions (REV 41,82) was wrong.

### 2.3 Observations

| Source | What | Endpoint |
|---|---|---|
| CDEC SQV (Squaw Valley Gold Coast, 8,200 ft) | SWE (sensor 3), snow depth (sensor 18), air temperature (sensor 4), hourly, PST | `cdec.water.ca.gov/dynamicapp/req/JSONDataServlet` |
| CDEC WC3 (Ward Creek #3, 6,750 ft) | same | same |
| Radiosonde KREV (Reno, 1,516 m) | latest 00Z/12Z sounding | `mesonet.agron.iastate.edu/json/raob.py` |
| Radiosonde KOAK (Oakland) | latest 00Z/12Z sounding; upwind Pacific inflow | same |
| Caltrans CWWP2 D3/D10 | chain-control checkpoints | `cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json` |

Earlier versions read CDEC sensor 82 (not reported at SQV) and the wrong JSON key, so depth showed 0.

**Resort snow report** (`resort_scraper.py`, enabled at the user's request): the resort's mountain-report page is drawn by a MtnPowder widget. The collector reads the widget's public configuration (`https://v4.mtnfeed.com/resorts/palisades-tahoe.json`: resort ID 61 and the feed token) at run time and requests `https://mtnpowder.com/feed/v3.json` the same way the page does. One feed covers both mountains:

| | Snow and weather areas | Lift areas |
|---|---|---|
| Palisades | Base 6,200 ft, Mid-Mountain 8,000 ft, Siberia Crest 8,700 ft | Palisades Peak, Emigrant Peak, High Camp, Granite Peak, Snow King Peak, KT Peak |
| Alpine | Station 4 Base 6,950 ft, Station 5 Mid 8,120 ft, Station 6 Summit 8,543 ft | Summit Peak, Scott/Lakeview Peak, Sherwood Bowl |

Fields used: new snow 24 h / 72 h / 7 d and settled depth per area (cleared new-snow boards), storm and season totals, surface condition, patrol report text, each lift's status, trail counts, and current weather at each station (temperature, dew point, humidity, wind, gust, sky). "--" values are treated as missing. Each run's resort totals are logged to `data/archive/resort_reports.json` for verification.

## 3. Query points and elevation handling

Each tier is queried at its own coordinates (`config/resorts.json`), checked against the Open-Meteo 90 m DEM:

| Resort | Tier | Lat, lon | Elevation used | DEM at point |
|---|---|---|---|---|
| Palisades | Base | 39.1970, −120.2356 | 6,200 ft | 6,214 ft (village) |
| Palisades | Mid | 39.1980, −120.2791 | 8,010 ft | 8,107 ft |
| Palisades | Summit | 39.1982, −120.2873 | 9,050 ft | 8,953 ft (Granite Chief; published 9,006 ft) |
| Alpine | Base | 39.1644, −120.2386 | 6,835 ft | 6,906 ft |
| Alpine | Mid | 39.1542, −120.2423 | 7,800 ft | 7,795 ft |
| Alpine | Summit | 39.1467, −120.2450 | 8,637 ft | 8,504 ft (Ward Peak) |

Open-Meteo selects the model grid cell nearest the coordinates and adjusts **temperature and humidity** from the cell's terrain height to the `elevation` parameter with a lapse rate. **Precipitation is not elevation-adjusted**, and neither is 10 m wind. Wind per tier therefore comes from the sounding: summit = pressure-level wind interpolated to summit height; base = 10 m model wind (sheltered); mid = 60% of the way from 10 m toward free-air. Gusts = wind × the model's 10 m gust factor (clamped 1.15–1.4).

Earlier versions queried all tiers at the village coordinates.

## 4. Derived quantities

### 4.1 Model sounding (summit point, 19 levels 1000–200 hPa)
Temperature, RH, geopotential height, vertical velocity (Open-Meteo sign: negative = rising; flipped so positive = ascent), wind. Derived per level: dew point (Magnus), RH w.r.t. ice, wet-bulb temperature from the psychrometric equation solved by bisection with pressure (valid at any temperature; the Stull 2011 fit is only valid to −20 °C and was replaced).

Levels below the terrain are model extrapolations; the skew-T shades everything below the base elevation.

### 4.2 Snow level and precipitation type
- **Wet-bulb zero (WBZ)**: lowest height where the wet bulb crosses 0 °C.
- **Snow level** = WBZ − 500 ft.
- **Snow fraction** at a tier: 1 at or above WBZ, 0 at WBZ − 1,000 ft, linear between; overridden by the tier's surface wet bulb (≤ 31 °F → snow, ≥ 36 °F → rain).
- **Sleet / freezing-rain risk**: a layer warmer than +0.5 °C, at least 1,000 ft deep, above a tier whose wet bulb is below 0 °C and whose snow fraction is below 1.
- **Chance of precipitation** = share of ensemble members with ≥ 0.01 in that hour (falls back to the model's own probability).

### 4.3 Snow/liquid ratio (SLR)
All methods use the same liquid and snow fraction.

| Method | Formula | Typical use | Behavior in the Sierra |
|---|---|---|---|
| **Cobb-style, adjusted (used)** | Crystal-habit SLR f(T) of each layer above the tier that is ice-saturated (RHice ≥ 95%) and rising, weighted by lift × thickness (after Cobb & Waldstreicher 2005); × wind factor (1 − 0.005 × (wind mph − 15), floor 0.75); capped at 9:1 when the tier wet bulb > −1 °C and 7:1 when > 0 °C | NWS forecast offices (Cobb method in BUFKIT) where vertical motion and RH profiles exist | Accounts for where crystals grow and for wind fragmentation |
| Cobb-style, unadjusted | habit × lift only | | Same as above without wind/melt |
| Kuchera | 12 + (271.16 − Tmax) if Tmax ≤ 271.16 K, else 12 + 2·(271.16 − Tmax); Tmax = warmest temperature between the tier and 500 hPa; 4–25 | Model snowfall maps (Pivotal, WeatherBell) | Fast and column-temperature aware, but ignores lift, cloud depth and wind; over-forecasts wind-driven, rimed Sierra snow |
| Fixed 10:1 | | Quick rule of thumb | Too high for wet/windy events, too low for cold dendritic snow |
| Open-Meteo snowfall field | the API's `snowfall` variable: water equivalent × 7 (≈ 7:1) | | Fixed; ignores the column |

Habit SLR f(T) (°C → SLR): 0 → 5, −2 → 8, −4 → 10, −6 → 12, −8 → 11, −10 → 12, −12 → 18, −14 → 26, −15 → 28, −16 → 26, −18 → 18, −20 → 14, −25 → 12, −30 → 10.

**Why the change from Kuchera.** Nov 18–19, 2026 storm, hindcast at SQV (8,200 ft) with the archived HRRR/GFS run: liquid 3.20 in vs 3.3–3.8 in SWE measured by the SQV pillow. References for snowfall: the resort's new-snow boards reported 42–46 in over 7 days (storm total 45 in), which with ~3.4–3.9 in of water implies ~11–13:1. (The SQV pillow's settled depth gain, +14 in, understates new snow at that wind-exposed site and is not used as the snowfall reference.)

| Method | Storm SLR | Snow |
|---|---|---|
| Kuchera | 14.6:1 | 47 in |
| Cobb-style, no wind adjustment | 15.2:1 | 49 in |
| Cobb-style, wind −1%/mph above 10 mph, floor 0.5 (first version) | 9.2:1 | 30 in |
| **Cobb-style, wind −0.5%/mph above 15 mph, floor 0.75 (current)** | **12.5:1** | **40 in** |
| Fixed 10:1 | 10:1 | 32 in |
| Resort boards | ~11–13:1 | 42–45 in |

700 hPa winds reached 66 mph. One storm is not a calibration; the verification archive (5.) tracks every forecast against the sensors and the resort's reports.

### 4.4 Dendritic growth zone (DGZ)
Heights where T = −12 °C and −18 °C, the matching pressures (log-p interpolation), mean RH (water and ice) and vertical motion sampled at bottom/middle/top. "Ice-saturated and rising": RHice ≥ 100% and vertical motion ≥ 10 cm/s. Cards summarize precipitating hours in the next 24 h (or all hours if none).

### 4.5 Consensus 24/48 h and ranges
Blend = 55% primary model summit snowfall + 45% NWS summit-cell gridded snowfall (model only if NWS has none; missing sources are dropped, never replaced). Range = ensemble 10th–90th percentile at the summit, widened only if the blend falls outside it.

### 4.6 Powder index
0.55 × max(24 h snow, 0.6 × 48 h snow) at the summit, minus 1.2 if summit gusts > 60 mph (0.5 if > 45); clamped 1–10. Wind can only lower it.

## 5. Verification (`verification.py`)

Each run saves the 48 h hourly forecast at each resort's sensor site (SQV, WC3) to `data/archive/` (one snapshot per 3 h, 21-day retention). When a window has passed, the forecast liquid and snow (used method, Kuchera, 10:1) are compared with the sensor's SWE and depth change over the same window (CDEC hours are PST; endpoint values are the median of readings within 2 h). Results accumulate in `data/verification_history.json`.

Each entry also carries the resort's reported new snow from the first resort report fetched within 5 days after the window ends (mid-mountain 7-day total and storm total). Those are rolling totals and can include snow outside the window; they are the best snowfall reference available (cleared boards), while the pillow SWE is the liquid reference.

Caveats: snow-pillow SWE does not capture rain that drains through the pack; sensor depth change is settled depth and understates new snowfall (typically 20–40% over 48 h), more so at wind-exposed sites.

The Nov 18 forecast was seeded from the previous pipeline: SQV forecast liquid 4.54 in vs 3.30 in measured (+38%); WC3 4.05 in vs 3.90 in (+4%).

## 6. Text on the page
All descriptive text is generated from the data by fixed rules, not written per forecast:

- Precipitation intensity: snow by snowfall rate (light < 0.5 in/hr, moderate 0.5–1, heavy ≥ 1); rain and mix by liquid rate (light < 0.10 in/hr, moderate 0.10–0.30, heavy > 0.30, AMS glossary).
- No precipitation: < 0.005 in/hr liquid; sky category from cloud cover (clear < 6%, mostly clear < 31%, partly cloudy < 56%, mostly cloudy < 94%, overcast ≥ 94%).
- High wind flag: sustained ≥ 40 mph or gust ≥ 58 mph (NWS High Wind Warning thresholds).
- Base rain risk: LOW if base > snow level + 500 ft, MODERATE if base within 500 ft above, HIGH if below.
- Lift status is the resort's (open / scheduled / closed / hold). Lifts on the configured wind-exposed list also show the peak daytime (8 AM–4 PM) summit gust forecast for the next 24 h, categorized < 45 / 45–64 / ≥ 65 mph.

## 7. Skew-T and crystal-habit diagrams
- Skew-T log-P: 45° skew, 1050–200 hPa. Dry adiabats θ = 240–440 K; pseudo-adiabats integrated from 1000 hPa. Sources: model sounding at the scrubber hour, or the latest REV/OAK radiosonde. Tier elevations are drawn at their interpolated pressure.
- Crystal habit: temperature 0 to −30 °C vs. supersaturation over ice, regions after Nakaya (1954) and Libbrecht (2005), water-saturation curve = es,water/es,ice − 1. Model levels above the base between 0 and −30 °C that are ice-supersaturated are plotted.

## 8. API
- `GET /api/snow` full dataset · `GET /api/status` refresh state · `POST /api/refresh` start a refresh · `GET /api/roads` · `GET /api/resorts`
