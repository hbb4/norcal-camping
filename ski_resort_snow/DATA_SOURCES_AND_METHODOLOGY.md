# Sierra Snow: Data Sources and Methodology

How every number on the dashboard is produced. Code references are to `collectors/`.

## 1. Refresh cycle

`python3 server.py` starts a full refresh immediately on launch, then:

| Job | Interval | Contents |
|---|---|---|
| Full refresh | 60 min | models, ensembles, model sounding, NWS, CDEC sensors, radiosondes, Caltrans, verification |
| Roads | 5 min | Caltrans CWWP2 only |
| Manual | Refresh button / `R` key | full refresh (`POST /api/refresh`) |

The page polls `GET /api/status` (every 1.5 s while a refresh runs, every 30 s otherwise), shows per-step progress, and reloads the dataset when a newer one is written. Every source carries `fetched_at_utc`.

**Failures never fall back to mock data.** If a source fails, the previous successful data for that source is kept and marked `stale`, with its original fetch time and the error; if there is none it is `error`. Mock data is only produced by `update_snow_data.py --mock`.

## 2. Sources

### 2.1 Numerical models

Seven models, each for 168 h. The page defaults to **NBM**; the model bar at the top switches the whole page to any one model, shown on its own.

| Page label | Source | Grid | Snowfall / SLR / snow level | Vertical profile |
|---|---|---|---|---|
| **NBM** (default) | NOAA NOMADS, native NBM v4 GRIB2 (`nbm_client.py`, `grib2_simple.py`) | 2.5 km | NBM's own ASNOW, SNOWLR, SNOWLVL | **none**: profile panels say so |
| ECMWF HRES | Open-Meteo `ecmwf_ifs` | 9 km | our method on the ECMWF IFS 0.25° column | ECMWF IFS 0.25° |
| ECMWF AIFS | Open-Meteo `ecmwf_aifs025_single` | 0.25° | our method | own, with vertical velocity |
| HRRR/GFS | Open-Meteo `gfs_seamless` | HRRR 3 km to ~47 h, then GFS | our method | own, with vertical velocity |
| ICON | Open-Meteo `icon_seamless` | 13 km | our method (no lift weighting) | own, no vertical velocity |
| UKMO | Open-Meteo `ukmo_seamless` | 10 km | our method | own, with vertical velocity (~150 h) |
| GEM | Open-Meteo `gem_seamless` | 10–15 km | our method (no lift weighting) | own, no vertical velocity |

**NBM** is read straight from NOAA: NOMADS's grib filter returns a small box around the resorts as simple-packed GRIB2 on the NBM Lambert conformal grid, decoded with the standard library. Fields at the nearest 2.5 km grid point to each tier and sensor: 2 m temperature, dew point and RH; 10 m wind, gust and direction; visibility; cloud cover; precipitation (APCP), snowfall (ASNOW), snow/liquid ratio (SNOWLR), snow level (SNOWLVL) and the probability of ≥ 0.254 mm precipitation. Hours 1–48 are hourly; after 48 h NBM's 6-hour values are used (accumulations spread evenly over the 6 hours, other fields interpolated; those hours are flagged). One 00/06/12/18Z cycle is downloaded once (~68 small files, a few minutes) and cached in `data/cache/`. NBM values are for the grid point's own terrain (no lapse-rate adjustment); the wet bulb shown for NBM is computed from its temperature and dew point.

**Ensembles** (`ensemble-api.open-meteo.com`): GEFS (NOAA, 31 members), ECMWF ENS (51) and ICON-EPS (40), about 120 members in all, precipitation only, at each tier's coordinates and elevation. Each member's hourly liquid is multiplied by the **selected model's** hourly snow-per-liquid factor at that tier (snow fraction × SLR; for NBM, NBM's snowfall ÷ precipitation), then summed into daily, cumulative, 24 h, 48 h and 7-day totals whose 10th/25th/50th/75th/90th percentiles drive the fan chart, the day tiles and the ranges. The share of members with ≥ 0.01 in in an hour is the chance of precipitation for the Open-Meteo models (NBM uses its own probability). The summary card draws the members' 24 h, 48 h and 7-day snow totals as a kernel density (Gaussian kernel, Silverman bandwidth with a floor of 2% of the axis), summit above the axis and base below, with the selected model's value as a tick. Because snow fraction and SLR come from one deterministic model, the spread describes precipitation amount and timing uncertainty only, not snow-level or SLR uncertainty.

**Units gotcha:** with `precipitation_unit=inch`, Open-Meteo returns all lengths in feet (freezing level, geopotential height, visibility). Surface queries use inches/feet; the sounding query does not set it, so heights are meters.

### 2.2 NWS (`nws_client.py`)

The Sierra crest is the boundary between NWS Reno (REV) and NWS Sacramento (STO). The base points of both resorts are in REV; both summit points fall in STO's grid.

- Alerts and the Area Forecast Discussion (Key Messages / Synopsis section) come from the office covering the **base** point (REV).
- Gridded snowfall (`snowfallAmount`, mm per interval) is summed over the next 24 h, 48 h and the full grid, both at the **summit** cell (STO, ~7,700 ft mean cell elevation) and the **base** cell (REV, ~6,300 ft). Both cells are shown under the snowfall distribution next to the model values. They are not blended into the model numbers.
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

### 4.1 Model sounding (where and how)
- **Where:** one model column at the summit point of each resort (Granite Chief 39.1982, −120.2873; Ward Peak 39.1467, −120.2450). Open-Meteo returns the grid column nearest that point; for 0.25° models that column averages ~25 km of terrain.
- **What:** temperature, RH, geopotential height, vertical velocity and wind on up to 19 pressure levels, 1000–200 hPa (models with fewer native levels return fewer). Open-Meteo's vertical velocity is negative for rising air; it is flipped so positive = ascent.
- **Derived per level:** dew point (Magnus), RH w.r.t. ice, wet bulb from the psychrometric equation solved with pressure.
- **Used for:** wet-bulb zero / snow level, freezing level, DGZ, sleet/freezing-rain check, SLR, free-air wind and free-air temperature at each tier height, skew-T, crystal-habit diagram.
- **Surface-only models:** NBM uses the GFS column and ECMWF HRES uses the ECMWF IFS 0.25° column; the page labels this ("NBM + GFS sounding").
- Levels below the terrain are model extrapolations; the skew-T shades everything below the base.

### 4.1b Tier temperature: 2 m vs. free air
Open-Meteo adjusts each model's 2 m temperature from the grid cell's terrain height to the requested elevation with a fixed lapse rate. That step cannot represent inversions. The model column can: on Nov 23–24, 2026 (06Z, HRRR column) the free-air temperature at 8,000 ft was 36 °F against 35 °F at the Palisades mid-mountain station, while the 2 m value was 28 °F. But free air was badly wrong in the valley cold pool (40.5 °F vs 24 °F at the base station) and at Alpine's summit station (35 °F vs 26 °F). The page therefore shows both (solid 2 m, dashed free air) in the elevation time series and compares them with the resort stations; choosing or blending them is a calibration item (TUNING_PLAN.md).

### 4.2 Snow level and precipitation type
- **Wet-bulb zero (WBZ)**: lowest height where the wet bulb crosses 0 °C.
- **Snow level** = WBZ − 500 ft.
- **Snow fraction** at a tier: 1 at or above WBZ, 0 at WBZ − 1,000 ft, linear between; overridden by the tier's surface wet bulb (≤ 31 °F → snow, ≥ 36 °F → rain).
- **Sleet / freezing-rain risk**: a layer warmer than +0.5 °C, at least 1,000 ft deep, above a tier whose wet bulb is below 0 °C and whose snow fraction is below 1.
- **Chance of precipitation** = share of ensemble members with ≥ 0.01 in that hour (falls back to the model's own probability).

### 4.3 Snow/liquid ratio (SLR)
All methods use the same liquid and snow fraction; only the ratio differs.

| Method | How | Strengths | Weaknesses |
|---|---|---|---|
| **Cobb-style (used)** | For each layer between the tier and 300 hPa that is ice-saturated (RHice ≥ 95%): crystal-habit SLR f(T) of the layer's mean temperature, weighted by upward motion × layer thickness. Models without vertical velocity (ICON, GEM): weighted by thickness only. Bounded 3–30:1. After Cobb & Waldstreicher (2005), the method used in BUFKIT. | Uses where crystals actually grow and how fast air rises through the DGZ | Ignores what happens below cloud: riming, wind fragmentation, melting; the f(T) curve here is an approximation of the published one |
| Cobb-style + wind/near-freezing adjustment (experimental) | Cobb-style × wind factor, where wind factor = 1 − 0.005 × (tier wind mph − 15), between 0.75 and 1; then capped at 9:1 if the tier wet bulb is above −1 °C and 7:1 above 0 °C | Direction of both effects is documented: wind fragments and packs crystals (e.g. Alcott & Steenburgh 2010); near 0 °C snow is wet and dense | **Coefficients are not calibrated.** They were set by hand and checked against one storm only, so they are shown for comparison and not used |
| Kuchera | 12 + (271.16 − Tmax) if Tmax ≤ 271.16 K, else 12 + 2·(271.16 − Tmax); Tmax = warmest temperature from the tier to 500 hPa; 4–25:1 | Simple, column-aware; common on model snowfall maps | Ignores lift, saturation, crystal habit and wind |
| Fixed 10:1 | | Climatological baseline | Wrong for both wet/windy and cold dendritic events |
| Open-Meteo snowfall field | API's `snowfall` = water equivalent × ~7 | Shows what the raw API says | Fixed ratio |

Habit SLR f(T) (°C → SLR): 0 → 5, −2 → 8, −4 → 10, −6 → 12, −8 → 11, −10 → 12, −12 → 18, −14 → 26, −15 → 28, −16 → 26, −18 → 18, −20 → 14, −25 → 12, −30 → 10.

**One-storm check (Nov 18–19, 2026; not a calibration).** Hindcast at SQV with the archived HRRR/GFS run: liquid 3.20 in vs 3.3–3.8 in SWE measured. The resort's new-snow boards reported 42–46 in over 7 days (storm total 45 in), implying ~11–13:1. Kuchera gave 14.6:1, unadjusted Cobb-style 15.2:1, fixed 10:1 10:1. One storm cannot set coefficients; `TUNING_PLAN.md` describes the multi-season calibration that will.

### 4.4 Dendritic growth zone (DGZ)
Heights where T = −12 °C and −18 °C, the matching pressures (log-p interpolation), mean RH (water and ice) and vertical motion sampled at bottom/middle/top. "Ice-saturated and rising": RHice ≥ 100% and vertical motion ≥ 10 cm/s. Cards summarize precipitating hours in the next 24 h (or all hours if none).

### 4.5 Forecast numbers and NWS
The 24 h, 48 h and 7-day numbers are the selected model's values at the base and summit, nothing else. Ranges and shapes come from the ensemble members. There is no blending with NWS: the NWS gridded snowfall (Reno's cell at the base point, Sacramento's cell at the summit point, since the crest is the office boundary) is listed separately under the summary and in Sources.

Chart axes (accumulation, hourly rate, wind, 7-day fan, distribution, elevation temperatures) are computed once per refresh across every model and elevation, so switching models or elevations never rescales them. The distribution axis ends at the larger of the highest model 7-day value and the 95th percentile of ensemble members across all models; members beyond it are counted at the right edge ("4 members > 40 in") rather than stretching the axis for a few outliers.

For a model with no vertical profile (NBM), the DGZ and skew-T panels say so. The moisture and crest-wind card still fills from surface fields: base mixing ratio from NBM's own temperature and dew point, summit wind from NBM's 10 m wind at the nearest grid point.

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
