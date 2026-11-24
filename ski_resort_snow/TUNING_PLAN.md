# Calibration plan: snow/liquid ratio, temperature downscaling, snow level

Goal: replace every hand-set coefficient in the pipeline with values fit on several winters of Palisades/Tahoe observations and checked out of sample. Until a parameter passes this process it stays out of the primary forecast (the wind/near-freezing SLR adjustment is currently shown only as "experimental").

## 1. What gets calibrated

| # | Quantity | Current method | Free parameters |
|---|---|---|---|
| 1 | Snow/liquid ratio | Cobb-style habit × lift, unadjusted | wind effect (form + slope + threshold), near-0 °C effect, habit curve scale, riming term |
| 2 | Tier temperature | model 2 m field, lapse-rate adjusted by Open-Meteo | blend weight between 2 m and free-air column temperature per tier, conditioned on stability |
| 3 | Rain/snow transition | snow level = WBZ − 500 ft; snow fraction linear over 1,000 ft below WBZ; surface wet-bulb overrides at 31 / 36 °F | WBZ offset, transition depth, wet-bulb thresholds |
| 4 | Precipitation amount | raw model QPF | per-model, per-tier multiplicative bias by lead time (optional) |
| 5 | Wind per tier | 10 m (base), free-air (summit), 60 % blend (mid) | blend weights per tier |

## 2. Ground truth

| Source | Variables | Elevation | Record | Use |
|---|---|---|---|---|
| CDEC SQV (Squaw Valley Gold Coast) | hourly SWE (3), depth (18), air temp (4) | 8,200 ft | multi-year hourly | liquid (SWE gain), temperature, rain-on-snow detection |
| CDEC WC3 (Ward Creek #3) | same | 6,750 ft | multi-year hourly | same, lower elevation |
| UC Berkeley Central Sierra Snow Lab (Donner Pass) | daily manual new-snow depth and new-snow water equivalent from cleared boards, precipitation, temperature | ~6,900 ft | decades | **the primary SLR reference**: measured new-snow density, not settled depth |
| NRCS SNOTEL sites near Palisades (via the AWDB web service) | hourly SWE, depth, gauge precipitation, temperature | 6,000–8,000 ft | multi-year | gauge precipitation (QPF bias), additional SWE/temperature samples |
| Palisades resort feed (logged by the pipeline every run since Nov 23, 2026) | new snow 24 h / 72 h / 7 d on boards at base and mid for both mountains, resort weather stations at 3 elevations each | 6,200–8,700 ft | going forward | SLR at the resorts, station temperature/wind for tiers 2 and 5 |
| Radiosondes REV, OAK (IEM archive) | full soundings 00Z/12Z | upper air | decades | check model column temperature, WBZ, DGZ |
| Optional: Synoptic/MesoWest (needs a free API token) | historical resort and RAWS station data, hourly | various | multi-year | temperature/wind history at the resort stations before our log started |

Station IDs and data availability for CSSL, SNOTEL and MesoWest still need to be confirmed through each service's catalog before download. None are assumed here.

## 3. Model data for past storms

- **Open-Meteo Historical Forecast API**: archived model output stitched from the most recent runs (short lead time), with pressure levels where the model provides them. This gives "best available forecast" profiles for the SLR, temperature and snow-level work, where lead time doesn't matter.
- **Open-Meteo Previous Runs API**: the same variables at fixed lead times (day 1–7) for recent seasons, for QPF bias and skill by lead time.
- Models: GFS/HRRR, ECMWF IFS 0.25°, AIFS, ICON, GEM and UKMO where archived. Some archives start later than others, so the sample size per model will differ.
- All downloads go to a local, git-ignored cache (`data/tuning/`) so the rate limit is hit once.

## 4. Building the sample

1. Winters 2021-22 through 2025-26 plus the current season (whatever each source covers).
2. A **storm-day** is a 24-hour window (12Z–12Z, matching manual board readings) with SWE gain ≥ 0.25 in at SQV or WC3, or ≥ 2 in of new snow on the CSSL board. Expected: roughly 100–250 storm-days.
3. For each storm-day and site: observed liquid, observed new snow (boards where available), observed SLR, temperatures, and every model feature the methods use. That covers the column temperature and RH-ice profile, vertical motion, Kuchera Tmax, Cobb raw SLR, 10 m / free-air / tier winds, surface T and Tw, WBZ, and liquid.
4. Quality control:
   - Drop days with pillow noise larger than the signal, rain-on-snow (depth falls while SWE rises), or missing hours.
   - Flag wind redistribution where the board and pillow disagree.

## 5. Fitting and testing

- **Baselines first, no fitting.** Score 10:1, Kuchera and Cobb unadjusted against observed SLR and snowfall. Metrics are bias, MAE, RMSE and MAE skill relative to 10:1.
- **Physically constrained adjustments.** Only monotone forms with few parameters are allowed: SLR decreasing with wind above a threshold, decreasing toward 0 °C, and optionally decreasing with liquid rate as a riming proxy. Each term is compared with published forms:
  - Alcott & Steenburgh (2010): Alta regression on temperature and wind.
  - Roebber et al. (2003): neural-network SLR.
  - Cobb & Waldstreicher (2005).
- **Out-of-sample only.** Leave-one-winter-out cross-validation. A term is adopted only if it improves out-of-sample MAE in most folds and its coefficient sign matches the physics. Report the fitted values with their spread across folds.
- **Temperature.** Fit the per-tier blend weight between 2 m and free-air temperature, split by a stability index (the 700 hPa vs. base temperature difference). Use the SQV/WC3 history and the logged resort stations.
- **Snow level.** Fit the WBZ offset and transition depth to events where SWE rose while the depth sensor did not (rain) vs. both rising (snow).

## 6. Output and how the dashboard uses it

- `config/calibration.json`: each fitted parameter with sample size, seasons used, cross-validated scores, and date fitted.
- The pipeline reads it. A calibrated method replaces "experimental" only when the file says it passed. The page shows "calibrated on N storm-days, winters X–Y, CV MAE …".
- The verification table keeps scoring live forecasts against the sensors and the resort boards, so drift shows up.

## 7. Work breakdown

| Step | Output | Rough effort |
|---|---|---|
| 1. Confirm data sources and station IDs; decide on a Synoptic token | source list | short |
| 2. Observation download scripts (CDEC, CSSL, SNOTEL, resort log) | `data/tuning/obs_*.csv` | 1 session |
| 3. Model archive download (Historical Forecast + Previous Runs) | `data/tuning/model_*.json` | 1 session (runs overnight under the rate limit) |
| 4. Feature extraction (reuse `open_meteo_client.py` functions) | storm-day table | 1 session |
| 5. Baseline scoring report | tables and plots | short |
| 6. Fit, cross-validate, write `calibration.json` | parameters and report | 1 session |
| 7. Wire into the dashboard | calibrated labels | short |

## 8. Known limits

- CSSL is at Donner Pass (~6,900 ft), not on the resort. It's the best SLR reference in the region, but its SLR may differ from the summits.
- Snow pillows lag and are noisy (±0.1–0.3 in), and depth sensors measure settled depth.
- Resort board totals are rolling and reported once or twice a day. Window alignment needs care.
- Historical-forecast archives are short-lead forecasts. Calibration fits the physics, not lead-time error. Lead-time effects need the Previous Runs API.
