# Calibration plan: elevation adjustment, snowfall, temperature, snow/liquid ratio

Goal: replace every hand-set choice in the pipeline with values fit on several winters of Palisades/Tahoe observations and checked out of sample. Until a method passes, it stays labeled (the wind/near-freezing SLR adjustment is shown only as "experimental").

**What changed (Nov 24, 2026):** NBM is now the primary forecast, read natively with its own snowfall, snow/liquid ratio and snow level, and moved from its 2.5 km cells to each tier's elevation using NBM's own hourly relationship with terrain (`nbm_downscale.py`). The SLR methods (Cobb, Kuchera, wind adjustment) now apply only to the Open-Meteo models. So the first calibration targets are NBM's adjusted snowfall and temperature at each tier, not SLR coefficients.

## 1. What gets calibrated

| # | Quantity | Current method | Question to answer |
|---|---|---|---|
| 1 | NBM snowfall at each tier | NBM cell value + local regression on terrain (elevation + cross-crest), refit hourly | Does the adjustment beat the raw cell against boards/pillows? Is there a residual bias by tier, lead time or storm type (snow level near the tier)? |
| 2 | Temperature at each tier (all models) | NBM: line fit through nearby cells at the tier height; Open-Meteo models: grid cell moved along the model's own column (section 9) | Calm-night errors of 8–14 °F above the valley floor (Nov 24). Fit the coupling weight c between 2 m and free-air temperature per tier (section 9). |
| 3 | Observed-minus-forecast at hour 0 | shown only, not carried forward | How long does an hour-0 error persist with lead time (by variable and tier)? If it decays predictably, apply a decaying correction; if not, leave forecasts alone. |
| 4 | NWS gridded snowfall at each tier | same regression on the NWS cells | Same verification as #1, to compare NWS and NBM skill at the tiers. |
| 5 | Open-Meteo models: snow/liquid ratio | Cobb-style habit × lift, unadjusted | wind effect, near-0 °C effect, habit curve scale, riming term (original plan, sections 5–6) |
| 6 | Open-Meteo models: rain/snow transition | snow level = WBZ − 500 ft; linear over 1,000 ft | WBZ offset, transition depth, surface wet-bulb thresholds |
| 7 | Wind per tier | 10 m (base), free-air (summit), 60% blend (mid) | blend weights per tier against the resort stations |
| 8 | Blend weights | Equal blend: equal; Skill blend (beta): 1/MAE from an Open-Meteo hindcast at SQV and WC3 (ICON 1.17, AIFS 1.12, HRRR/GFS 1.09, HRES 0.98, GEM 0.82, UKMO 0.81; 62 cold wet site-days from Mar 2025); Short-range blend: NBM 3, HRRR/GFS 4 to 18 h falling to 1 by 48 h, the other five 1 each; ECMWF pair: equal; a long-lead skill blend is fitted with `blend_weights.py --hindcast --lead-day N --apply blend_skill_long` (`config/sources.json` → `blends`) | Skill weights per lead day from the per-model archive (`data/archive/models/`, from Nov 24, 2026) against SQV snow-water gains (`blend_weights.py`, weight ∝ 1/MAE, ≥ 15 cold wet days per model and lead). Adopt only if leave-one-month-out MAE of the blend improves. |

## 2. Ground truth (confirmed Nov 24, 2026, by test requests)

**Snow pillows and depth sensors, hourly, no authentication.** NRCS AWDB REST API (`wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data`, elements WTEQ, SNWD, PREC, TOBS; inches, °F, local standard time; PREC accumulates from Oct 1 and is noisy, so it needs filtering). CDEC's SQV and WC3 are copies of the same SNOTEL feeds.

Download: `python3 nrcs_sync.py` (update; backfills WY2021 onward on first run) writes `data/tuning/nrcs/<CDEC code>/WY<yyyy>.csv`, one row per hour of the water year with blanks where AWDB has no value. All seven sites report fixed PST (`dataTimeZone` −8). Suspect values are requested too (AWDB drops them by default) and every value keeps its flags: qc V validated, E edited, S suspect, C bias-corrected (air temperature); qa R raw, P provisional, A approved. Quality control happens when the sample is built (section 4), not in the download. Updates fetch only values AWDB inserted or changed since the last sync (`insertOrUpdateBeginDate`), so NRCS edits and approvals flow in. AWDB keeps the whole hourly record, so this needs no cron job; run an update before building a sample.

| Triplet | Name (CDEC) | Lat, lon | Elev ft | km from Palisades | Hourly depth from |
|---|---|---|---|---|---|
| 784:CA:SNTL | Palisades Tahoe (SQV) | 39.1899, −120.2658 | 8,010 | 2.7 | 1998 |
| 848:CA:SNTL | Ward Creek #3 (WC3) | 39.1354, −120.2186 | 6,750 | 7.0 | 2003 |
| 809:CA:SNTL | Tahoe City Cross (TCC) | 39.1716, −120.1536 | 6,760 | 7.6 | 2003 |
| 834:CA:SNTL | Truckee #2 (TK2) | 39.3009, −120.1841 | 6,500 | 12.4 | 2002 |
| 428:CA:SNTL | Central Sierra Snow Lab (CSL) | 39.3257, −120.3681 | 6,890 | 18.3 | 2005 |
| 724:CA:SNTL | Rubicon #2 (RP2) | 38.9993, −120.1314 | 7,560 | 23.8 | 2003 |
| 541:CA:SNTL | Independence Lake (IDP) | 39.4275, −120.3134 | 8,340 | 26.5 | 1978 |

Non-SNOTEL CDEC stations with hourly snow sensors nearby: HYS Huysink (6,600 ft), VVL Van Vleck (6,700 ft), MDW Meadow Lake (7,200 ft).

**SQV location (resolved Nov 24, 2026):** the sensor point now uses the NRCS numbers (8,010 ft, 39.1899, −120.2658), since NRCS owns the station. CDEC lists 8,200 ft at 39.194, −120.276; the CDEC station ID is still used for the hourly data feed.

**New-snow density (the snow/liquid ratio reference).** UC Berkeley Central Sierra Snow Lab (6,890 ft): new snow on boards at 08:00 and 16:00 PST, summed per day; snowpack SWE at 09:00 (from SNOTEL 428 at 00:00 since WY2021). The archive README does not state when the 24-hour precipitation is read; in the archive, new snow on date D correlates best with precipitation on D (r 0.53, against 0.34 for D−1), so the two do not cover exactly the same 24 hours. `cssl_sync.py` handles both sources; output goes to `data/tuning/cssl/` (not committed).

- **Archive:** Dryad doi:10.6078/D1941T (CC0), one CSV per water year, WY1971–WY2025 (no WY2020), republished each October. The metadata API is public, but file downloads need a browser (the page uses a bot check) or a Dryad API account (ORCID login, then an API key on the account page). Download the zip in the browser, then `python3 cssl_sync.py import` unpacks it, lists each file's columns in `archive/v<date>/columns.json` and writes one combined table, `archive/daily.csv` (`cssl_sync.py daily` rebuilds it).
- **Archive columns (confirmed Nov 24, 2026, v20251001):** date; air temperature max/min (°C); 24-hour and season precipitation (mm); % of precipitation as snow and as rain; new snow and season snow (cm); snowpack depth (cm); snowpack SWE (cm); remarks. There is **no new-snow water column**: the water in new snow is 24-hour precipitation × % as snow. The % as snow is given from WY1988 on (blank before), so WY1971–1987 is usable only where temperature makes all-snow certain. Quirks handled by the importer: UTF-8 byte-order marks, an unnamed duplicate of New Snow in WY2021, "T" traces in any numeric column (0, flagged for new snow and precipitation), thousands separators in season totals; one SWE typo ("0'0") is left empty.
- **First look (WY1988–2025, all-snow days):** 723 days with ≥10 cm new snow and ≥10 mm precipitation: snow/liquid ratio p10 5.6, median 10.0, p90 20.5. Day-by-day pairs are noisy because of the timing offset above (Nov 18–19, 2020 reads 15:1 then 1.3:1; the two-day total is 5:1). 167 all-snow storms (consecutive snow days, ≥20 cm and ≥20 mm): p10 7.0, median 9.7, p90 14.8. Fit on storm totals; use daily values only with matching model windows.
- **Current season:** the cssl.berkeley.edu home page embeds the whole water year as daily series (accumulated snowfall, accumulated precipitation, snowpack SWE) and shows the latest 8 AM board, including **24-hour snowfall SWE**, which is shown for the current day only. `cssl_sync.py` rewrites `season_WY<yyyy>.json` and appends new board readings to `board_log.csv`.
- **Schedule:** `scripts/cssl_cron.sh` runs the sync and a Dryad version check (no download). Cron entry: `30 9,13,18 * * *`; three runs cover a laptop that was asleep at 9:30. A missed day loses only that day's board SWE; the daily series is republished in full.

**Resort observations.**
- New-snow boards: the resort feed, logged by the pipeline every run since Nov 23, 2026 (`data/archive/resort_reports.json`).
- Weather stations: MesoWest network 212, 15-minute temperature, dew point, humidity and wind. Station IDs:

  | ID | Location | Elevation |
  |---|---|---|
  | OVBOW | Olympic Valley base | 6,237 ft |
  | BMTSV | Belmont, mid-mountain | 8,000 ft |
  | SIBSV | Siberia | 8,700 ft |
  | RHBAM | Alpine Roundhouse bottom | 6,950 ft |
  | SCTAM | Alpine Scott top | 8,120 ft |
  | SUMAM | Alpine summit | 8,399 ft |

  History needs a Synoptic token. Decision (Nov 24, 2026): no Synoptic trial. Station history only matters for hindcasts of past seasons, and those use SNOTEL hourly air temperature (all seven sites above, at known elevations) instead.
- MesoWest's public site shuts down on Dec 31, 2026. The dashboard does not use it: live readings come from the resort feed. The shutdown only removes a free, token-less way to browse past station data; the data itself stays with Synoptic.
- Going forward, the pipeline logs the same stations from the resort feed every run (`data/archive/station_pairs.jsonl`, paired with the forecast), so the station record for verification builds from Nov 24, 2026 on.

**Other stations** (api.weather.gov, about 7 days of history only): CWOP Olympic Valley D9019 (0.6 km), KTRK, Homewood HMDC1, Slide Mountain SLIDE (9,650 ft).

**Radiosondes:** Reno (REV), from the IEM archive, for checking column temperature and the wet-bulb zero.

## 3. Model data for past storms

- **NBM archive on AWS** (`noaa-nbm-grib2-pds`, no authentication):
  - Core files from 2020-09-29 12Z.
  - Versions:

    | Version | First cycle |
    |---|---|
    | v4.0 | 2020-09-29 |
    | v4.1 | 2023-01-17 |
    | v4.2 | 2024-05-15 |
    | v4.3 | 2025-05-27 |
    | v5.0 | 2026-05-05 (hourly output to 48 h) |

  - Fields:
    - 1-hour and 6-hour APCP and ASNOW are present in every version.
    - The snow/liquid ratio is local parameter 1/233 in every version (confirmed Nov 24, 2026). The index names it SNOWLR from late 2022 and only by number before; the live client reads the same code.
    - SNOWLVL is absent in early v4.0 (not in the Jan 2021 or Dec 2021 files; present by Dec 2022).
  - Files are 120–200 MB, so only the needed messages are read using byte ranges from the `.idx` file (about 1 MB each).
  - These full-grid files use complex packing with second-order spatial differencing (template 5.3), primary missing values and scanning mode 0x50 (rows south to north, alternate rows reversed). `grib2_complex.py` decodes them; the field is integrated from its first point, so decoding stops after the box's last cell (52% of the grid, 0.3–0.5 s per field).
  - Only about two thirds of each message is downloaded: the first request reads the headers and group tables, the second stops at the byte where the box ends. About 4 MB and 4 s per forecast hour for six fields.
  - Checked against NOMADS (Nov 24, 2026 12Z, f024/f132/f144): all six fields identical at all 72 live-box cells, including precipitation and snowfall.
  - Values are kept for an extended box of 22 × 31 cells around all seven SNOTEL sites (the live 72-cell box only covers SQV and WC3), in the live layout, with the live cells marked, so the live elevation adjustment can be reproduced exactly and run at every site.
  - Because the versions changed, results are reported per version.
- **Open-Meteo Historical Forecast API**, for the other models, from these dates:

  | Model | From |
  |---|---|
  | ncep_nbm_conus | 2024-10-08 (surface only) |
  | gfs_seamless | 2021 (with pressure levels) |
  | ncep_hrrr_conus | 2018 |
  | ecmwf_ifs025 | 2024-02 |
  | icon, gem | about 2022-11 |
  | ukmo | 2022 |

  Some snowfall fields are missing in some months.
- **Open-Meteo Previous Runs API**: fixed lead times (day 1–7) for surface variables. It rejects pressure-level variables. Precipitation starts around January 2024.
- **Rate limit:** Open-Meteo's free tier is 5,000 calls an hour and 10,000 a day, and multi-model or many-variable requests count as several calls. On Nov 24 the quota for this machine was already used up. The live dashboard's hourly refresh of seven models is the likely cause. Downloads should run overnight, cached in `data/tuning/`, and the live refresh may need to fetch the non-default models less often.

## 4. Building the sample

1. Winters 2021-22 through 2025-26 plus the current season.
2. A **storm-day** is a 24-hour window (12Z–12Z) with SWE gain ≥ 0.25 in at SQV or WC3 or ≥ 2 in of new snow on a board.
   - From SNOTEL (`nbm_archive_sync.py storm-days`, Nov 24, 2026): 425 storm-days in WY2021–WY2027, 397 confirmed (the trigger site's gauge rose ≥ 0.05 in, or at least two other SNOTEL sites gained ≥ 0.1 in). The other 28, mostly March–May, look like pillow noise. Each 04:00 PST value is the median of the raw 02:00–06:00 readings, so one noisy hour can't create a storm-day.
   - Board-only storm-days (resort feed) exist only from Nov 23, 2026.
   - Storm-days only sample stormy weather. Temperature calibration (item 2) also needs fair-weather inversion days such as Nov 24, 2026; add a sample of dry days before fitting temperature.
3. For each storm-day and site:
   - the observed liquid, new snow and snow/liquid ratio;
   - the station temperatures;
   - the raw NBM cell value and the elevation-adjusted value;
   - the HRRR/GFS free-air temperature at the site height;
   - for the Open-Meteo models, every SLR feature (column temperature and RH over ice, vertical motion, Kuchera Tmax, raw Cobb SLR, winds, wet-bulb zero).
4. Quality control:
   - Drop pillow noise larger than the signal, rain-on-snow (SWE rises while depth falls), and missing hours.
   - SNOTEL hourly (checked Nov 24, 2026, WY2021–WY2027, seven sites): drop qc S. The physically impossible snow-water readings are all flagged S (206 in at SQV on May 6, 2024; 356–360 in at TK2 on Jul 19, 2021; 130 in at CSL on Aug 27, 2021).
   - SNOTEL hourly mixes two series. The 00:00 value is the NRCS-edited daily value (qc E, often qa A) and the other hours are raw readings; at IDP on Mar 29, 2023 the 00:00 value is 72.9 in between raw readings of 70.9 in. 291 of 306 one-hour "spikes" of 2 in or more are these midnight values. Compute hourly gains from the raw hours only (skip the 00:00 value) and use the daily edited values as a check on storm totals.
   - Flag wind redistribution where the board and pillow disagree.

## 5. Fitting and testing

- **Baselines first, no fitting:**
  - NBM raw cell vs adjusted, scored at each site and tier.
  - For the Open-Meteo models: 10:1, Kuchera and unadjusted Cobb.
  - Metrics: bias, MAE, RMSE and MAE skill relative to the raw cell (or to 10:1 for SLR).
- **Elevation adjustment checks:**
  - Does the regression radius and weighting matter (5, 7, 10 km)?
  - Does including the cross-crest term help at the tiers?
  - How much does extrapolating beyond the highest neighbor (Palisades summit, +450 ft) cost?
- **Physically constrained terms only:** monotone forms with few parameters, compared with published forms:
  - Alcott & Steenburgh (2010)
  - Roebber et al. (2003)
  - Cobb & Waldstreicher (2005)
- **Out of sample only:**
  - Leave-one-winter-out cross-validation.
  - A term is adopted only if it improves out-of-sample MAE in most folds and its sign matches the physics.
  - Report the spread of each fitted value across folds.
- **Temperature:**
  - Errors of the adjusted 2 m temperature and the HRRR/GFS free-air temperature at the resort stations, split by a stability index (700 hPa minus base temperature).
  - A blend weight is fit only if it wins out of sample.

## 6. Output and how the dashboard uses it

- `config/calibration.json`: each fitted parameter with sample size, seasons, model versions, cross-validated scores and date fitted.
- The pipeline reads it. A calibrated method replaces the current one only when the file says it passed, and the page shows "calibrated on N storm-days, winters X–Y, CV MAE …".
- The verification table keeps scoring live forecasts against the sensors and the resort boards, so drift shows up.

## 7. Work breakdown

| Step | Output | Status |
|---|---|---|
| 1. Confirm data sources and station IDs; decide on a Synoptic token | section 2 above | **done Nov 24, 2026**: SQV uses NRCS numbers, no Synoptic token; CSSL columns confirmed (section 2) |
| 2. Observation download scripts (NRCS AWDB hourly, CSSL, resort log) | `data/tuning/cssl/`, `data/tuning/nrcs/` | CSSL done (`cssl_sync.py`, cron); NRCS AWDB hourly done Nov 24, 2026 (`nrcs_sync.py`, seven sites, WY2021 on); resort log runs with the pipeline |
| 3. NBM archive reader (byte-range `.idx` + GRIB2 template 5.3 decoder) and storm-day extraction over the same box | `data/tuning/storm_days.json`, `data/tuning/nbm/cycles/nbm_*.json`, `data/tuning/nbm/terrain.json` | reader done Nov 24, 2026 (`nbm_archive_sync.py`); pilot of one storm per NBM version done; full day-1 download (397 storm-days, about 6.7 GB, 100 min) not yet run |
| 4. Open-Meteo Historical Forecast pulls (overnight, cached) | `data/tuning/model_*.json` | after 3 |
| 5. Baseline scoring report (raw vs adjusted NBM, NWS, SLR methods) | `calibration_baseline.py` → `data/tuning/reports/nbm_baseline.md` | NBM raw vs adjusted at the seven SNOTEL sites: started Nov 24, 2026 (first 16 storm-days: temperature MAE 2.79 → 2.35 °F with the adjustment, liquid unchanged); full day-1 sample when the download completes. NWS gridded has no archive; SLR methods need the Open-Meteo pulls (step 4). |
| 6. Fit, cross-validate, write `calibration.json` | parameters and report | |
| 7. Wire into the dashboard | calibrated labels | |

## 7b. How to run the remaining steps

All commands run from `ski_resort_snow/`. Outputs go to `data/tuning/` (not committed). Long downloads can be stopped and rerun; finished files are skipped. To keep a long run going with the lid open and the screen off: `caffeinate -i python3 …`; to keep it running after closing the terminal: `nohup caffeinate -i python3 … > data/tuning/<name>.log 2>&1 &`.

1. SNOTEL hourly up to date (seconds): `python3 nrcs_sync.py`
2. Storm-days from SNOTEL (seconds): `python3 nbm_archive_sync.py storm-days`
3. NBM day-1 forecasts for every confirmed storm-day (step 3; about 400 cycles, ~6.7 GB, 2-6 h depending on the connection; 149 cycles were already on disk on Nov 24, 2026): `python3 -u nbm_archive_sync.py fetch | tee data/tuning/nbm/fetch.log`. Day 2 and 3 as well (about 3x more): add `--leads 1,2,3`.
4. NBM baseline scores at the SNOTEL sites (step 5; about a minute): `python3 calibration_baseline.py --md` → `data/tuning/reports/nbm_baseline.md`.
5. Skill-blend weights, short lead (a few minutes the first time, then cached): `python3 blend_weights.py --hindcast --write --apply blend_skill`. Long lead, e.g. day 3: `python3 blend_weights.py --hindcast --lead-day 3 --write --apply blend_skill_long`. `--apply` writes the weights into `config/sources.json`; the blend appears or changes on the next data refresh (`python3 update_snow_data.py`, or the running server's hourly refresh).
6. Weights from the live per-model archive (once ~15 cold, wet days have accumulated): `python3 blend_weights.py --write`.
7. Temperature coupling weights (grows with every pipeline run): `python3 station_bias.py`.
8. Precipitation skill, days and whole storms, raw vs bias-corrected, categorical, blends (seconds, from the cache): `python3 skill_report.py --md`; long lead after step 5's long-lead fit: `python3 skill_report.py --lead-day 3 --md`.
9. Neighborhood test (interpolation and the precipitation elevation shift): `python3 neighborhood_hindcast.py fetch --plan` to see the size (default WY2026-WY2027, 9 points: 216 requests, about 1,600 Open-Meteo calls, ~5 minutes), then `python3 neighborhood_hindcast.py fetch`, then `python3 neighborhood_hindcast.py score --md`. More seasons: `--seasons 2023,2024,2025,2026,2027` (about 4,000 calls; split over two days if the dashboard is also refreshing). Then `python3 neighborhood_hindcast.py fit` to see the residual multipliers, and `fit --apply` to write them and the Corrected blend into `config/sources.json` (seconds, from the cache).
10. Not built yet: step 4 (Open-Meteo Historical Forecast pulls of the full surface and column fields for the SLR terms) and the HRRR pressure-level archive for free-air temperature in past winters.

## 8. Known limits

- CSSL is at Donner Pass (6,890 ft), 18 km from the resort. Its snow/liquid ratio may differ from the summits.
- Snow pillows lag and are noisy (±0.1–0.3 in), and depth sensors measure settled depth.
- Resort board totals are rolling and reported once or twice a day. Window alignment needs care.
- The NBM leave-one-out check (7-day snowfall MAE 1.64 → 0.45 in) shows the adjustment reproduces NBM's own field. Only observations can show whether NBM's field is right.
- Historical-forecast archives are short-lead. Lead-time effects need the Previous Runs API or the NBM archive at fixed leads.

## 9. Temperature at the tiers (Nov 24, 2026)

**How each tier's temperature is computed now.**
- NBM: every hour, a distance-weighted line of temperature against terrain height is fit through the ~25 NBM cells within 7 km, and the line is evaluated at the tier's own height. Until Nov 24 the nearest cell's own value was moved along that line instead, so Palisades mid and summit inherited one cell (7,726 ft) and its local deviation. The fitted line did better on both checks: leave-one-out on the live box, MAE 1.10 → 0.92 °F (7-day snowfall 0.49 → 0.41 in); SNOTEL air temperature at seven sites in five archived storm cycles, MAE 1.77 → 1.47 °F, bias +0.91 → +0.54 °F. Weighting cells by elevation as well as distance did not help further.
- Open-Meteo models: until Nov 24, Open-Meteo's own downscaling moved 2 m temperature from the model cell to the tier with a fixed 6.5 °C/km (measured: HRRR/GFS 6.7, ECMWF 6.5, GEM 6.6 °C/km). The pipeline now requests the raw cell (`elevation=nan`), finds the cell's height on the model's own column from its surface pressure, and moves temperature and dew point by the column's change between the two heights. The cells are far from the tiers: for the Palisades summit (9,049 ft) HRRR's cell is at 8,038 ft, GEM 7,127, UKMO 7,002, ECMWF 6,984, AIFS 6,829 and ICON 6,739 ft. Wet bulb and humidity are recomputed at the tier.
- Free air: the model column's temperature at the station's height (HRRR/GFS for NBM). Shown beside the 2 m value in the stations table.

**What the stations show (night of Nov 23–24, calm and clear).** The 2 m values (NBM, and any model's 2 m field) were 8–14 °F too cold at stations above the valley floor; the free-air temperature at the same height was within 1–4 °F:

| Station | Measured | NBM 2 m | Free air |
|---|---|---|---|
| Palisades base, valley floor 6,200 ft, calm | 22 °F | 24 °F | 40 °F |
| Palisades mid 8,000 ft, 18 mph | 34 °F | 20 °F | 35 °F |
| Palisades Siberia 8,700 ft | 30 °F | 18 °F | 33 °F |
| Alpine base 6,950 ft | 37 °F | 24.5 °F | 38 °F |
| Alpine mid 8,120 ft | 33 °F | 24 °F | 36 °F |
| Alpine summit 8,543 ft | 25 °F | 22.6 °F | 34 °F |

Correction (Nov 24, later): the "free air" values for Palisades base and Alpine base and mid were below the HRRR/GFS column's own terrain (about 8,000 ft at the summit point), where pressure-level values are the model's surface temperature extrapolated downward, not free air; the page now leaves free air blank below the column's ground, and the coupling weights for those stations need a column whose terrain is below them. The mid and summit comparisons stand. By late morning (mixed boundary layer) every method was within about 4 °F. The cause is not the elevation adjustment: each model cell has its own calm-night surface layer, while real slopes and ridges above the valley cold pool are ventilated by wind. No re-fit of the 2 m field can create an inversion it doesn't have. The SQV SNOTEL sensor (8,010 ft, near Palisades mid) read 34 °F at 01:00 PST, the same as the mid station, while WC3 in its valley read 21 °F, so SNOTEL can stand in for the mid tier when hindcasting past winters.

**Correction to fit.** A coupling weight per tier:

  T_tier = T_free_air + c · (T_2m − T_free_air)

c ≈ 0 behaves like free air (ventilated slope), c ≈ 1 like the model's 2 m value (sheltered valley floor). From the three logged runs: Palisades base 1.1, mid 0.05, summit 0.26; Alpine base 0.10, mid 0.28, summit 0.73. Three runs are far too few. c may also depend on wind speed (coupling) and on the model's own stability (T_free_air − T_2m). `python3 station_bias.py` reports the station-minus-model error of both temperatures per tier, night and day, the best-fit c, and the 2 m error by lead time; it grows with every pipeline run (`data/archive/station_pairs.jsonl`, hourly while `server.py` runs).
- Static part: c per tier (and per wind class), fit on station pairs going forward and on past winters with SNOTEL temperatures (SQV ≈ mid, WC3/TK2 valley floors, IDP/RP2/CSL) against the NBM archive's 2 m field and the HRRR archive's free-air temperature (pressure-level TMP from AWS, read with the same byte-range decoder, so no Open-Meteo quota). This needs fair-weather days in the NBM sample, not only storm-days.
- Dynamic part: the hour-0 error decaying with lead time (below). In the first night the 2 m error fell from +7.7 °F at hour 0 to +4.0 at 1–3 h and +1.8 at 4–17 h, mostly because the night ended.
- Adoption: only after at least ~30 nights per tier and only if leave-one-week-out MAE improves at most tiers, as for every other term.

## 9b. Precipitation skill at the pillows (Nov 24, 2026)

`python3 skill_report.py --md` → `data/tuning/reports/skill_report.md`. Cached Open-Meteo hindcasts (short lead), SQV and WC3 pillows, cold days, whole storms = runs of consecutive confirmed storm-days; every number on held-out seasons. Five models (no AIFS), WY2023-WY2027, 379 cold site-days:

| Blend | Day MAE | Storm MAE | Day CSI (≥ 0.5 in) | POD | FAR |
|---|---|---|---|---|---|
| Equal, raw | 0.52 | 0.63 | 0.62 | 0.69 | 0.13 |
| 1/MAE weights, raw (today's Skill blend) | 0.51 | 0.63 | 0.63 | 0.69 | 0.12 |
| Equal, bias-corrected | 0.45 | 0.51 | 0.72 | 0.84 | 0.16 |
| 1/MAE weights, bias-corrected | 0.45 | 0.51 | 0.72 | 0.84 | 0.16 |

- Bias correction (one multiplier per model and pillow, fitted on the other seasons) cuts storm-total error 19% and daily error 13%, and raises the hit rate from 0.69 to 0.84 for a small rise in false alarms. Weighting by skill adds nothing once the members are corrected, and very little before. The six-model sample (95 days, three seasons) agrees.
- Multipliers (latest fit): ECMWF HRES 1.4-1.5, AIFS 1.3, HRRR/GFS 1.1-1.3, ICON 1.0-1.5, GEM 1.3 (SQV) and 2.8-3.3 (WC3), UKMO 1.8-2.0. ICON's varies most between seasons, so correcting it over-corrects some seasons.
- A corrected blend needs multipliers for the resort tiers, not just the two pillows. Done with the elevation shift below (the Corrected blend).

**Ways to handle the dry bias.**
1. Multiplicative correction per model and site (above). Simple and robust; doesn't transfer to places without a pillow.
2. Quantile mapping: map each model's distribution of daily amounts onto the pillow's, which corrects light and heavy days differently. Needs more storms per site.
3. Regime-dependent correction: separate multipliers by flow direction (upslope south-west vs other), snow level or storm type (atmospheric river vs cold trough), where the orographic deficit differs.
4. An elevation shift for precipitation (below), leaving a smaller residual for 1-3.

**Ways to shift precipitation to a site's height.**
- a. The model's own neighborhood: fit each day's precipitation against cell height and distance across the crest over the cells around the site, and evaluate at the site (the NBM method). `neighborhood_hindcast.py` fetches the cells and scores this against the single cell, an inverse-distance mean and the height-matched cell. A test pull showed the gradient exists in the models: HRRR/GFS 6.73 in at a 7,516 ft cell vs 7.37 in at 8,077 ft over the same five days.
  - Result, five seasons (WY2023-WY2027, about 395 cold site-days per model at SQV and WC3; AIFS 95 from spring 2025). Report: `data/tuning/reports/neighborhood.md`. Lake Tahoe cells come back at 0 ft and are taken at the lake surface (6,225 ft). The two-season first look (64 site-days) overstated the gains.
  - Without a multiplier, the elevation line removes most of the storm-total dry bias: ECMWF HRES -0.42 to +0.06 in, UKMO -0.70 to -0.16, ICON -0.30 to -0.09, HRRR/GFS -0.17 to -0.08, AIFS -0.48 to -0.36. GEM is the exception (-0.41 to -0.58): its slope through its own cells runs the wrong way at the pillows.
  - Residual multipliers after the shift are small and close to height-independent: pooled over both pillows ECMWF HRES 1.04, HRRR/GFS 1.12, ICON 1.17, UKMO 1.24, AIFS 1.25, GEM 1.71. By pillow they are lower at SQV (0.95-1.20, GEM 1.61) than at WC3 (1.27-1.95), the lower site, so what is left is the site (Ward Creek is wetter than its height), not height.
  - Equal blend of five members (no AIFS), held-out seasons, 379 cold site-days: storm MAE 0.63 in with each model's own cell, 0.54 with the elevation line alone, 0.53 with the line and a pooled multiplier, 0.50 with the own cell and a pooled multiplier. Daily MAE 0.52 / 0.48 / 0.45 / 0.45; days >= 0.5 in caught (POD) 0.69 / 0.75 / 0.83 / 0.82. Six members on 95 common days: 0.76 / 0.60 / 0.53 / 0.45.
  - Decision (Nov 24, 2026): the elevation line is the first-level correction and one pooled residual multiplier per model goes on top. At the pillows a multiplier alone scores as well, but a multiplier alone is fitted to each pillow's height and doesn't carry to tiers 1,000-2,800 ft away; after the shift the multiplier is small and has no height trend, so it carries. The inverse-distance mean was not adopted (no gain over the line once corrected).
  - Built: `collectors/precip_shift.py` (the method, shared by the hindcast and the live forecast), `neighborhood_hindcast.py fit --apply` (writes `precip_correction` and the `blend_corrected` entry into `config/sources.json`), the Corrected blend in the model selector, and corrected versions of the six single models (`<model>.corrected.json`, the Corrected precip switch, corrected totals in the model table; archived as `<model>_corrected` for live scoring). Held-out storm error per model, own cell → corrected: HRES 0.64 → 0.51 in, UKMO 0.81 → 0.57, GEM 0.72 → 0.58, AIFS 0.74 → 0.53, HRRR/GFS 0.63 → 0.59, ICON 0.57 → 0.59. The live fetch adds one 3x3 neighborhood request per model per resort (precipitation only, 168 h); Palisades and Alpine share every model's but HRRR/GFS's, so 7 requests and about 63 Open-Meteo calls per refresh.
  - Limits: the fit is short-lead (Historical Forecast API) and applied at every lead; HRRR/GFS's neighborhood is HRRR's 3 km grid, which falls inside one or two GFS cells after 48 h, so the shift fades to nothing there and only the residual applies. Re-fit after each season: `python3 neighborhood_hindcast.py fetch --seasons <new WY>`, then `fit --apply`.
  - Nov 25, 2026: GEM out of the Equal blend (raw blend storm MAE 0.634 with it, 0.622 without; corrected 0.530 either way, so it stays in the Corrected blend). RRFS (Open-Meteo `ncep_rrfs_conus`) added to every multi-model blend; it has no hindcast, so `member_models()` (the hindcast list) now comes from the model table's `hindcast` flag instead of the Equal blend, and refits keep RRFS at weight 1.0 / multiplier 1.0. Score it once the live per-model archive has a season of RRFS forecasts.
- b. NBM ratio: NBM is 2.5 km and statistically calibrated; scale a coarse model by NBM(site) / NBM(model cell footprint) for the same period. Event-specific, but ties every model to NBM's structure.
- c. PRISM ratio: scale by the ratio of PRISM 30-year normal precipitation (800 m) at the site and over the model cell. Static and climatological; needs the PRISM normals (free download).
- d. Observed gradient from the pillow network (seven sites, 6,500-8,340 ft): too few sites and too much local exposure to fit alone, but a check on a-c.

## 10. Observed vs. forecast at hour 0

The page now shows station readings at hour 0 beside the model at each tier. When they differ a lot, three options:

1. **Show only (current).** Make the disagreement visible and don't touch the forecast.
2. **Decaying correction.** Add the hour-0 error to the forecast and shrink it with lead time: error(t) = error(0) · e^(−t/τ). τ is fit per variable and tier from the logged station-vs-forecast pairs. This is standard practice for temperature in the first ~6–12 hours, and is only worthwhile if the errors persist.
3. **Regime switch.** For temperature in inversions, switch to the free-air column temperature when the stations show the inversion and the 2 m field does not.

Until about one season of station-vs-forecast pairs exists (the pipeline logs both every hour), option 1 stays. τ and the regime test then go through the same cross-validation as everything else.
