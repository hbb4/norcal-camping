"""Open-Meteo collector: named NWP models, model soundings and snow diagnostics.

Data actually requested (all through api.open-meteo.com, no key):

* Primary deterministic forecast: ``gfs_seamless`` = NOAA HRRR (3 km) for the
  first ~48 h, NOAA GFS 0.25 deg after that. Queried at each tier's own
  coordinates and elevation (base / mid / summit) plus the snow-sensor site.
* Model sounding for the same model at the summit coordinates: temperature,
  relative humidity, geopotential height, vertical velocity and wind on 19
  pressure levels (1000-200 hPa).
* Comparison runs at the summit: HRRR, NBM, GFS, ECMWF IFS, ICON, GEM
  (precipitation only), each with its latest run time from Open-Meteo's
  model metadata.
* Ensembles (ensemble-api.open-meteo.com): GEFS, ECMWF ENS and ICON-EPS
  member precipitation at each tier (~120 members).

Elevation handling: Open-Meteo picks the model grid cell nearest the
coordinates and adjusts temperature / humidity from the grid-cell terrain
height to the ``elevation`` we pass, using a lapse rate. Precipitation and
wind are NOT elevation-adjusted; wind is handled below with pressure-level
winds, precipitation is taken as the model gives it.

Derived per hour and tier:

* Wet-bulb zero height (WBZ) from the sounding; snow level = WBZ - 500 ft.
  Snow fraction: 1 at/above WBZ, 0 at 1,000 ft below it, overridden by the
  tier's surface wet bulb (<= 31 F all snow, >= 36 F all rain).
* Sleet / freezing-rain flag: a layer warmer than +0.5 C, at least 1,000 ft
  deep, above a tier whose wet bulb is below 0 C.
* Snow/liquid ratio (SLR), three methods:
    - cobb_adj (primary): Cobb & Waldstreicher (2005)-style. Each cloudy
      (ice-saturated), rising layer above the tier contributes a
      crystal-habit SLR for its temperature, weighted by lift x thickness.
      Then a wind-fragmentation factor (tier wind) and near-freezing caps.
    - kuchera: from the warmest temperature between the tier and 500 hPa.
    - fixed 10:1.
  Open-Meteo's own ``snowfall`` field (fixed ~7:1) is kept as model_field.
* DGZ (-12 to -18 C): heights, pressures, RH w.r.t. water and ice, lift.
* Tier wind: base = model 10 m wind (sheltered valley), summit = free-air
  wind interpolated from pressure levels, mid = 60 % toward free-air.
"""

import json
import math
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

M_TO_FT = 3.28084
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200]
LEVEL_VARS = ["temperature", "relative_humidity", "geopotential_height", "vertical_velocity", "wind_speed", "wind_direction"]
TIMELINE_HOURS = 48
FORECAST_HOURS = 168

PRIMARY_MODEL = {"id": "gfs_seamless", "label": "HRRR 3 km (0-48 h) then GFS 0.25 deg", "meta": ["ncep_hrrr_conus", "ncep_gfs025"]}
COMPARISON_MODELS = [
    {"id": "ncep_hrrr_conus", "label": "HRRR", "provider": "NOAA/NCEP", "grid": "3 km", "meta": "ncep_hrrr_conus"},
    {"id": "ncep_nbm_conus", "label": "NBM (National Blend)", "provider": "NOAA/NWS", "grid": "2.5 km", "meta": "ncep_nbm_conus"},
    {"id": "gfs_global", "label": "GFS", "provider": "NOAA/NCEP", "grid": "0.11-0.25 deg (13-25 km)", "meta": "ncep_gfs025"},
    {"id": "ecmwf_ifs025", "label": "ECMWF IFS", "provider": "ECMWF", "grid": "0.25 deg (~25 km)", "meta": "ecmwf_ifs025"},
    {"id": "icon_seamless", "label": "ICON", "provider": "DWD (Germany)", "grid": "13 km (global)", "meta": "dwd_icon"},
    {"id": "gem_seamless", "label": "GEM", "provider": "ECCC (Canada)", "grid": "10-15 km", "meta": "cmc_gem_gdps"},
]
ENSEMBLE_MODELS = "gfs_seamless,ecmwf_ifs025,icon_seamless"

# Approximate snow/liquid ratio of crystals grown at a given temperature (C),
# after Cobb & Waldstreicher (2005): plates/columns near 0 to -10 C, peak for
# dendrites near -15 C, moderate again below -20 C.
HABIT_SLR = [(0, 5), (-2, 8), (-4, 10), (-6, 12), (-8, 11), (-10, 12), (-12, 18), (-14, 26), (-15, 28),
             (-16, 26), (-18, 18), (-20, 14), (-25, 12), (-30, 10), (-40, 8)]


# --------------------------------------------------------------------------
# Thermodynamic helpers
# --------------------------------------------------------------------------
def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def wet_bulb_stull_c(t_c: float, rh: float) -> float:
    """Stull (2011) wet-bulb approximation, valid for RH 5-99%, T -20..50 C."""
    rh = max(5.0, min(99.0, rh))
    return (t_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + math.atan(t_c + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)


def wet_bulb_psychro_c(t_c: float, td_c: float, p_hpa: float) -> float:
    """Wet-bulb temperature from the psychrometric equation, solved by bisection.

    e(Td) = es(Tw) - 0.00066 * p * (1 + 0.00115 Tw) * (T - Tw). Valid at any temperature,
    unlike Stull (2011), which is only fitted for -20..50 C."""
    if td_c >= t_c:
        return t_c
    e = es_water(td_c)
    lo, hi = td_c, t_c
    for _ in range(40):
        mid = (lo + hi) / 2
        f = es_water(mid) - 0.00066 * p_hpa * (1 + 0.00115 * mid) * (t_c - mid) - e
        if f > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def es_water(t_c: float) -> float:
    return 6.112 * math.exp(17.67 * t_c / (t_c + 243.5))


def es_ice(t_c: float) -> float:
    return 6.112 * math.exp(22.46 * t_c / (t_c + 272.62))


def dewpoint_c(t_c: float, rh: float) -> float:
    rh = max(1.0, min(100.0, rh))
    g = math.log(rh / 100.0) + 17.67 * t_c / (t_c + 243.5)
    return 243.5 * g / (17.67 - g)


def rh_ice(t_c: float, rh_w: float) -> float:
    """RH with respect to ice from RH with respect to water."""
    if t_c >= 0:
        return rh_w
    return rh_w * es_water(t_c) / es_ice(t_c)


def std_pressure_hpa(height_m: float) -> float:
    return 1013.25 * (1.0 - 2.25577e-5 * height_m) ** 5.25588


def mixing_ratio_g_kg(dew_c: float, p_hpa: float) -> float:
    e = es_water(dew_c)
    return 621.97 * e / max(1.0, p_hpa - e)


def kuchera_slr(t_max_k: float) -> float:
    """Kuchera snow/liquid ratio from the warmest temperature (K) in the column."""
    if t_max_k > 271.16:
        slr = 12.0 + 2.0 * (271.16 - t_max_k)
    else:
        slr = 12.0 + (271.16 - t_max_k)
    return max(4.0, min(25.0, slr))


def habit_slr(t_c: float) -> float:
    if t_c >= 0:
        return HABIT_SLR[0][1]
    for (t0, s0), (t1, s1) in zip(HABIT_SLR, HABIT_SLR[1:]):
        if t1 <= t_c <= t0:
            return s0 + (s1 - s0) * (t_c - t0) / (t1 - t0)
    return HABIT_SLR[-1][1]


def wind_factor(wind_mph: float) -> float:
    """Crystal fragmentation / wind packing: no change below 15 mph, -0.5 % per mph above, floor 0.75.

    Tuned on the Nov 18-19 2026 storm (hindcast at SQV vs resort new-snow boards);
    the earlier -1 %/mph above 10 mph (floor 0.5) under-forecast that storm by ~30 %."""
    return max(0.75, min(1.0, 1.0 - 0.005 * (wind_mph - 15.0)))


def _interp_height_for_value(heights: List[float], values: List[float], target: float) -> Optional[float]:
    """Lowest height (m) where `values` crosses `target`, scanning bottom-up."""
    for i in range(len(heights) - 1):
        v0, v1 = values[i], values[i + 1]
        if v0 is None or v1 is None:
            continue
        if (v0 - target) * (v1 - target) <= 0 and v0 != v1:
            frac = (target - v0) / (v1 - v0)
            return heights[i] + frac * (heights[i + 1] - heights[i])
    return None


def _interp_at_height(heights: List[float], values: List[float], h: float) -> Optional[float]:
    pts = [(z, v) for z, v in zip(heights, values) if z is not None and v is not None]
    if not pts:
        return None
    if h <= pts[0][0]:
        return pts[0][1]
    for (z0, v0), (z1, v1) in zip(pts, pts[1:]):
        if z0 <= h <= z1:
            return v0 + (v1 - v0) * (h - z0) / max(1e-6, z1 - z0)
    return pts[-1][1]


def _pressure_at_height(levels: List[Dict[str, Any]], h: float) -> Optional[float]:
    """Log-pressure interpolation of the height (m) on the model column."""
    pts = [(lv["z"], math.log(lv["p"])) for lv in levels if lv.get("p")]
    v = _interp_at_height([p[0] for p in pts], [p[1] for p in pts], h)
    return math.exp(v) if v is not None else None


def _val(arr, i, default=None):
    if arr is None or i >= len(arr) or arr[i] is None:
        return default
    return float(arr[i])


def _iso(t: str) -> str:
    return t + "Z" if not t.endswith("Z") else t


class OpenMeteoClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
    META_URL = "https://api.open-meteo.com/data/{model}/static/meta.json"
    USER_AGENT = "SierraSnowDashboard/3.0"

    def __init__(self, timeout_sec: int = 20):
        self.timeout_sec = timeout_sec
        self._meta_cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def fetch_resort_forecast(self, tiers: Dict[str, Dict[str, Any]], sensor: Optional[Dict[str, Any]] = None,
                              progress=None) -> Dict[str, Any]:
        """tiers: {"base"|"mid"|"summit": {"lat", "lon", "elevation_m", "note"}}; sensor: same shape plus "id"."""
        say = progress or (lambda msg: None)
        labels = {"base": "Base", "mid": "Mid mountain", "summit": "Summit"}
        try:
            say("model surface forecasts")
            surface = {k: self._query_surface(t["lat"], t["lon"], t["elevation_m"]) for k, t in tiers.items()}
            say("model sounding")
            summit = tiers["summit"]
            upper = self._query_upper_air(summit["lat"], summit["lon"])
            profile = self._build_vertical_profile(upper)

            say("ensembles")
            ensembles = {}
            for k, t in tiers.items():
                try:
                    ensembles[k] = self._query_ensemble(t["lat"], t["lon"], t["elevation_m"])
                except Exception:
                    ensembles[k] = None

            exposure = {"base": 0.0, "mid": 0.6, "summit": 1.0}
            parsed = {k: self._build_tier(surface[k], profile, labels[k], tiers[k]["elevation_m"], exposure[k], ensembles[k]) for k in tiers}

            sensor_out = None
            if sensor:
                try:
                    s_surface = self._query_surface(sensor["lat"], sensor["lon"], sensor["elevation_m"])
                    s_tier = self._build_tier(s_surface, profile, sensor.get("id", "sensor"), sensor["elevation_m"], 0.6, None)
                    sensor_out = {"id": sensor.get("id"), "lat": sensor["lat"], "lon": sensor["lon"],
                                  "elevation_ft": round(sensor["elevation_m"] * M_TO_FT),
                                  "hourly": [{k: s[k] for k in ("time", "precip_in", "snowfall_rate_in_hr", "slr", "slr_kuchera", "snow_fraction", "temp_f")}
                                             for s in s_tier["_steps"][:TIMELINE_HOURS]],
                                  "liquid_48h_inches": s_tier["liquid_48h_inches"], "snow_48h_inches": s_tier["snow_48h_inches"],
                                  "slr_methods": s_tier["slr_methods"]}
                except Exception:
                    sensor_out = None

            say("model comparison")
            comparison = self._model_comparison(summit, parsed["summit"]["_steps"])
            primary_runs = [self._model_meta(m) for m in PRIMARY_MODEL["meta"]]

            sounding = self._summarize_sounding(profile, parsed, tiers)
            sounding_hourly = [{"time": p["time"], "levels": p["_skewt"]} for p in profile[:TIMELINE_HOURS]]
            for p in profile:
                p.pop("_levels", None)
                p.pop("_skewt", None)

            for k in parsed:
                parsed[k].pop("_steps", None)
            s_tl = parsed["summit"]["hourly_timeline_48h"]
            fl48 = [p["freezing_level_ft"] for p in profile[:TIMELINE_HOURS] if p["freezing_level_ft"]]
            now = datetime.now(timezone.utc).isoformat()
            return {
                "status": "success",
                "source": f"Open-Meteo: {PRIMARY_MODEL['label']}",
                "timestamp_utc": now,
                "fetched_at_utc": now,
                "primary_model": {**PRIMARY_MODEL, "runs": primary_runs},
                "model_comparison": comparison,
                "query_points": {k: {"lat": t["lat"], "lon": t["lon"], "elevation_ft": round(t["elevation_m"] * M_TO_FT), "note": t.get("note", "")}
                                 for k, t in tiers.items()},
                "base": {k: v for k, v in parsed["base"].items() if k != "hourly_timeline_48h"},
                "mid": {k: v for k, v in parsed["mid"].items() if k != "hourly_timeline_48h"},
                "summit": {k: v for k, v in parsed["summit"].items() if k != "hourly_timeline_48h"},
                "base_48h_inches": parsed["base"]["snow_48h_inches"],
                "mid_48h_inches": parsed["mid"]["snow_48h_inches"],
                "summit_48h_inches": parsed["summit"]["snow_48h_inches"],
                "summit_7d_total_inches": parsed["summit"]["snow_7d_total_inches"],
                "peak_gust_summit_mph": round(max([s["gust_mph"] for s in s_tl] or [0.0]), 1),
                "avg_freezing_level_ft": round(sum(fl48) / len(fl48)) if fl48 else None,
                "elevation_timelines": {k: parsed[k]["hourly_timeline_48h"] for k in tiers},
                "hourly_timeline": s_tl,
                "vertical_profile": profile[:TIMELINE_HOURS],
                "sounding_hourly": sounding_hourly,
                "atmospheric_sounding": sounding,
                "sensor_point": sensor_out,
                "methodology": {
                    "snowfall": "liquid x snow fraction (wet-bulb zero height) x SLR (Cobb-style habit x lift, wind and near-freezing adjusted)",
                    "slr_alternates": "Kuchera and fixed 10:1 shown for comparison; model_field is Open-Meteo's snowfall variable (fixed ~7:1)",
                    "wind": "summit: pressure-level wind at summit height; base: model 10 m wind; mid: 60% toward free-air; gusts = wind x model 10 m gust factor",
                    "elevation": "temperature/humidity lapse-rate adjusted to each tier elevation; precipitation not elevation-adjusted",
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "source": "Open-Meteo",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_message": f"{type(e).__name__}: {e}",
            }

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _get(self, url_base: str, params: Dict[str, str], timeout: Optional[int] = None) -> Dict[str, Any]:
        url = f"{url_base}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            raise RuntimeError(f"HTTP {e.code}: {body}") from None

    def _query_surface(self, lat: float, lon: float, elevation_m: int) -> Dict[str, Any]:
        return self._get(self.BASE_URL, {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": str(elevation_m),
            "hourly": ",".join([
                "snowfall", "precipitation", "precipitation_probability",
                "temperature_2m", "dew_point_2m", "relative_humidity_2m",
                "wet_bulb_temperature_2m", "freezing_level_height", "cloud_cover",
                "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
            ]),
            "models": PRIMARY_MODEL["id"],
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT",
            "precipitation_unit": "inch", "wind_speed_unit": "mph", "temperature_unit": "fahrenheit",
        })

    def _query_upper_air(self, lat: float, lon: float) -> Dict[str, Any]:
        hourly = [f"{v}_{p}hPa" for p in PRESSURE_LEVELS for v in LEVEL_VARS]
        return self._get(self.BASE_URL, {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
            "hourly": ",".join(hourly), "models": PRIMARY_MODEL["id"],
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT",
            "wind_speed_unit": "mph",   # heights stay in meters, temperatures in C
        }, timeout=self.timeout_sec * 2)

    def _query_ensemble(self, lat: float, lon: float, elevation_m: int) -> Dict[str, Any]:
        return self._get(self.ENSEMBLE_URL, {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": str(elevation_m),
            "hourly": "precipitation", "models": ENSEMBLE_MODELS,
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0",
            "timezone": "GMT", "precipitation_unit": "inch",
        }, timeout=self.timeout_sec * 2)

    def _model_meta(self, meta_id: str) -> Dict[str, Any]:
        if meta_id in self._meta_cache:
            return self._meta_cache[meta_id]
        out = {"model": meta_id}
        try:
            req = urllib.request.Request(self.META_URL.format(model=meta_id), headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as r:
                m = json.loads(r.read().decode("utf-8"))
            iso = lambda ts: datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) else None
            out.update({"run_init_utc": iso(m.get("last_run_initialisation_time")),
                        "run_available_utc": iso(m.get("last_run_availability_time")),
                        "update_interval_h": round((m.get("update_interval_seconds") or 0) / 3600, 1)})
        except Exception:
            pass
        self._meta_cache[meta_id] = out
        return out

    def _model_comparison(self, point: Dict[str, Any], primary_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Liquid from each named model at the summit point; snow uses the primary
        forecast's hourly snow fraction x SLR so differences reflect precipitation only."""
        try:
            d = self._get(self.BASE_URL, {
                "latitude": f"{point['lat']:.4f}", "longitude": f"{point['lon']:.4f}", "elevation": str(point["elevation_m"]),
                "hourly": "precipitation", "models": ",".join(m["id"] for m in COMPARISON_MODELS),
                "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT", "precipitation_unit": "inch",
            })
        except Exception as e:
            return [{"label": "comparison unavailable", "error": str(e)}]
        h = d.get("hourly", {})
        factor = [s["snow_fraction"] * s["slr"] for s in primary_steps]
        out = []
        for m in COMPARISON_MODELS:
            arr = h.get(f"precipitation_{m['id']}") or []
            hours = sum(1 for x in arr if x is not None)
            row = {k: m[k] for k in ("id", "label", "provider", "grid")}
            row.update(self._model_meta(m["meta"]))
            row["hours_available"] = hours
            # Model metadata older than 3 days is not trustworthy; don't show it as a run time
            try:
                if row.get("run_init_utc") and (datetime.now(timezone.utc) - datetime.fromisoformat(row["run_init_utc"])).days >= 3:
                    row["run_init_utc"] = row["run_available_utc"] = None
                    row["run_note"] = "run time not reported by Open-Meteo"
            except Exception:
                pass
            if hours == 0:
                row["error"] = "no precipitation data for this location"
            else:
                def liq(n):
                    vals = [x for x in arr[:n] if x is not None]
                    return round(sum(vals), 2) if vals else None
                row.update({"liquid_24h": liq(24), "liquid_48h": liq(48), "liquid_7d": liq(168),
                            "covers_48h": hours >= 47, "covers_7d": hours >= 160})
                snow = [(arr[i] or 0.0) * factor[i] for i in range(min(len(arr), len(factor)))]
                row["snow_48h"] = round(sum(snow[:48]), 1)
                row["snow_7d"] = round(sum(snow[:168]), 1)
            out.append(row)
        return out

    # ------------------------------------------------------------------
    # Sounding
    # ------------------------------------------------------------------
    def _build_vertical_profile(self, upper: Dict[str, Any]) -> List[Dict[str, Any]]:
        uh = upper.get("hourly", {})
        out = []
        for i, t in enumerate(uh.get("time", [])):
            levels = []
            for p in PRESSURE_LEVELS:
                z = _val(uh.get(f"geopotential_height_{p}hPa"), i)
                tc = _val(uh.get(f"temperature_{p}hPa"), i)
                rh = _val(uh.get(f"relative_humidity_{p}hPa"), i)
                if z is None or tc is None or rh is None:
                    continue
                # Open-Meteo vertical velocity: negative = rising. Flip so + = ascent.
                w = -_val(uh.get(f"vertical_velocity_{p}hPa"), i, 0.0)
                td = dewpoint_c(tc, rh)
                levels.append({"p": p, "z": z, "t": tc, "rh": rh, "rhi": rh_ice(tc, rh), "tw": wet_bulb_psychro_c(tc, td, p),
                               "td": td, "w": w,
                               "ws": _val(uh.get(f"wind_speed_{p}hPa"), i), "wd": _val(uh.get(f"wind_direction_{p}hPa"), i)})
            levels.sort(key=lambda lv: lv["z"])
            zs = [lv["z"] for lv in levels]

            wbz_m = _interp_height_for_value(zs, [lv["tw"] for lv in levels], 0.0)
            fzl_m = _interp_height_for_value(zs, [lv["t"] for lv in levels], 0.0)
            column_cold = bool(levels) and levels[0]["tw"] <= 0 and wbz_m is None

            dgz_bot = _interp_height_for_value(zs, [lv["t"] for lv in levels], -12.0)
            dgz_top = _interp_height_for_value(zs, [lv["t"] for lv in levels], -18.0)
            dgz = {}
            if dgz_bot is not None and dgz_top is not None and dgz_top > dgz_bot:
                samples = (dgz_bot, (dgz_bot + dgz_top) / 2, dgz_top)
                avg = lambda key: sum(_interp_at_height(zs, [lv[key] for lv in levels], h) for h in samples) / 3
                dgz = {"rh": avg("rh"), "rhi": avg("rhi"), "w": avg("w"),
                       "p_bot": _pressure_at_height(levels, dgz_bot), "p_top": _pressure_at_height(levels, dgz_top)}

            def ft(m):
                return round(m * M_TO_FT) if m is not None else None

            wbz_ft = ft(wbz_m) if wbz_m is not None else (ft(levels[0]["z"]) if column_cold else None)
            out.append({
                "time": _iso(t),
                "freezing_level_ft": ft(fzl_m),
                "wet_bulb_zero_ft": wbz_ft,
                "wbz_below_lowest_level": column_cold,
                "snow_level_ft": (wbz_ft - 500) if wbz_ft is not None else None,
                "dgz_base_ft": ft(dgz_bot) if dgz else None,
                "dgz_top_ft": ft(dgz_top) if dgz else None,
                "dgz_base_hpa": round(dgz["p_bot"]) if dgz.get("p_bot") else None,
                "dgz_top_hpa": round(dgz["p_top"]) if dgz.get("p_top") else None,
                "dgz_thickness_ft": ft(dgz_top - dgz_bot) if dgz else None,
                "dgz_rh_pct": round(dgz["rh"]) if dgz else None,
                "dgz_rhi_pct": round(dgz["rhi"]) if dgz else None,
                "dgz_lift_cm_s": round(dgz["w"] * 100, 1) if dgz else None,
                "_levels": levels,
                "_skewt": [[lv["p"], round(lv["z"]), round(lv["t"], 1), round(lv["td"], 1),
                            round(lv["wd"]) if lv["wd"] is not None else None,
                            round(lv["ws"]) if lv["ws"] is not None else None,
                            round(lv["w"] * 100, 1)] for lv in sorted(levels, key=lambda x: -x["p"])],
            })
        return out

    # ------------------------------------------------------------------
    # Per-tier timeline
    # ------------------------------------------------------------------
    def _build_tier(self, data: Dict[str, Any], profile: List[Dict[str, Any]], level_name: str, elevation_m: int,
                    exposure: float = 1.0, ensemble: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        h = data.get("hourly", {})
        times = h.get("time", [])
        elev_ft = round(elevation_m * M_TO_FT)
        p_hpa = std_pressure_hpa(elevation_m)
        ens_pop = self._ensemble_pop(ensemble, len(times)) if ensemble else None

        steps = []
        cum = cum_model = cum_k = cum_10 = 0.0
        for i, t in enumerate(times):
            prof = profile[i] if i < len(profile) else {}
            levels = prof.get("_levels", [])
            above = [lv for lv in levels if lv["z"] >= elevation_m]

            precip = _val(h.get("precipitation"), i, 0.0)
            model_snow = _val(h.get("snowfall"), i, 0.0)
            model_pop = _val(h.get("precipitation_probability"), i)
            pop = ens_pop[i] if ens_pop else (int(model_pop) if model_pop is not None else (100 if precip >= 0.01 else 0))
            temp_f = _val(h.get("temperature_2m"), i, 30.0)
            dew_f = _val(h.get("dew_point_2m"), i, temp_f - 4)
            rh = _val(h.get("relative_humidity_2m"), i, 85.0)
            wb_f = _val(h.get("wet_bulb_temperature_2m"), i)
            if wb_f is None:
                wb_f = c_to_f(wet_bulb_stull_c(f_to_c(temp_f), rh))
            t_c, wb_c = f_to_c(temp_f), f_to_c(wb_f)

            # Snow fraction from position relative to the wet-bulb zero height
            wbz = prof.get("wet_bulb_zero_ft")
            if wbz is None:
                frac = 1.0 if wb_f <= 33.0 else 0.0
            else:
                frac = max(0.0, min(1.0, (elev_ft - (wbz - 1000)) / 1000.0))
            if wb_f <= 31.0:
                frac = 1.0
            elif wb_f >= 36.0:
                frac = 0.0

            # Warm layer aloft over a sub-freezing tier -> sleet / freezing rain risk
            warm = [lv for lv in above if lv["t"] > 0.5]
            warm_depth = (max(lv["z"] for lv in warm) - min(lv["z"] for lv in warm)) if len(warm) >= 2 else (300 if warm else 0)
            ice_risk = bool(warm) and warm_depth >= 300 and wb_c < 0 and frac < 1.0

            # --- Snow/liquid ratio methods -------------------------------------
            col = [t_c] + [lv["t"] for lv in above if lv["p"] >= 500]
            slr_k = kuchera_slr(max(col) + 273.15)
            num = den = 0.0
            for a, b in zip(above, above[1:]):
                if a["p"] < 300:
                    break
                rhi = (a["rhi"] + b["rhi"]) / 2
                w = (a["w"] + b["w"]) / 2
                if rhi >= 95 and w > 0:
                    wt = w * (b["z"] - a["z"])
                    num += wt * habit_slr((a["t"] + b["t"]) / 2)
                    den += wt
            slr_cobb = num / den if den > 0 else slr_k

            # Wind at tier height
            lv_wind = [lv for lv in levels if lv["ws"] is not None and lv["wd"] is not None]
            zs = [lv["z"] for lv in lv_wind]
            ws10 = _val(h.get("wind_speed_10m"), i, 0.0)
            g10 = _val(h.get("wind_gusts_10m"), i, ws10 * 1.4)
            if lv_wind:
                free_air = _interp_at_height(zs, [lv["ws"] for lv in lv_wind], elevation_m)
                u = _interp_at_height(zs, [-lv["ws"] * math.sin(math.radians(lv["wd"])) for lv in lv_wind], elevation_m)
                v = _interp_at_height(zs, [-lv["ws"] * math.cos(math.radians(lv["wd"])) for lv in lv_wind], elevation_m)
                wd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
                ws = ws10 + exposure * max(0.0, free_air - ws10)
            else:
                free_air, ws, wd = ws10, ws10, _val(h.get("wind_direction_10m"), i, 0.0)
            gust_factor = max(1.15, min(1.4, g10 / ws10)) if ws10 > 3 else 1.3
            gust = max(g10, ws * gust_factor)

            slr = slr_cobb * wind_factor(ws)
            if wb_c > -1.0:
                slr = min(slr, 9.0)
            if wb_c > 0.0:
                slr = min(slr, 7.0)
            slr = max(3.0, slr)

            snow = precip * frac * slr
            cum += snow
            cum_model += model_snow
            cum_k += precip * frac * slr_k
            cum_10 += precip * frac * 10.0

            if precip < 0.005 and pop < 20:
                phase = "dry"
            elif ice_risk:
                phase = "ice"
            elif frac >= 0.9:
                phase = "snow"
            elif frac <= 0.1:
                phase = "rain"
            else:
                phase = "mix"

            dpd = temp_f - dew_f
            steps.append({
                "time": _iso(t),
                "precip_in": round(precip, 3),
                "snowfall_rate_in_hr": round(snow, 2),
                "cumulative_snow_inches": round(cum, 2),
                "model_snowfall_in_hr": round(model_snow, 2),
                "model_cumulative_inches": round(cum_model, 2),
                "kuchera_cumulative_inches": round(cum_k, 2),
                "slr": round(slr, 1),
                "slr_cobb_raw": round(slr_cobb, 1),
                "slr_kuchera": round(slr_k, 1),
                "snow_fraction": round(frac, 2),
                "precip_phase": phase,
                "precip_phase_label": {"dry": "None", "snow": "Snow", "mix": "Rain/snow", "rain": "Rain", "ice": "Sleet/freezing rain risk"}[phase],
                "precip_probability": pop,
                "pop_source": "ensemble" if ens_pop else "model",
                "chance_snow_pct": round(pop * frac),
                "chance_rain_pct": round(pop * (1 - frac)),
                "temp_f": round(temp_f, 1),
                "wet_bulb_f": round(wb_f, 1),
                "dew_point_f": round(dew_f, 1),
                "dew_point_depression_f": round(dpd, 1),
                "relative_humidity_pct": round(rh),
                "mixing_ratio_g_kg": round(mixing_ratio_g_kg(f_to_c(dew_f), p_hpa), 2),
                "cloud_cover_pct": _val(h.get("cloud_cover"), i),
                "wind_mph": round(ws, 1),
                "gust_mph": round(gust, 1),
                "wind_dir_deg": round(wd),
                "model_10m_wind_mph": round(ws10, 1),
                "free_air_wind_mph": round(free_air, 1),
                "freezing_level_ft": prof.get("freezing_level_ft") or (round(_val(h.get("freezing_level_height"), i)) if _val(h.get("freezing_level_height"), i) is not None else None),
                "snow_level_ft": prof.get("snow_level_ft"),
                "wet_bulb_zero_ft": prof.get("wet_bulb_zero_ft"),
                "warm_layer_aloft": bool(warm),
            })

        def total(key, n):
            return round(sum(s[key] for s in steps[:n]), 1)

        def liquid_weighted(key, n):
            wet = [s for s in steps[:n] if s["precip_in"] >= 0.01 and s["snow_fraction"] > 0]
            tot = sum(s["precip_in"] for s in wet)
            return round(sum(s[key] * s["precip_in"] for s in wet) / tot, 1) if tot > 0 else None

        daily = self._daily_rollup(steps)
        ens = self._ensemble_summary(ensemble, steps, daily) if ensemble else None
        if ens:
            by_date = {d["date"]: d for d in ens["daily"]}
            for d in daily:
                e = by_date.get(d["date"])
                if e:
                    d.update({"snow_p10": e["p10"], "snow_p25": e["p25"], "snow_p50": e["p50"], "snow_p75": e["p75"],
                              "snow_p90": e["p90"], "prob_6in": e["prob_6in"], "prob_12in": e["prob_12in"]})

        liq48 = sum(s["precip_in"] * s["snow_fraction"] for s in steps[:48])
        liq7 = sum(s["precip_in"] * s["snow_fraction"] for s in steps)
        return {
            "level": level_name,
            "elevation_ft": elev_ft,
            "ensemble": ens,
            "snow_24h_inches": total("snowfall_rate_in_hr", 24),
            "snow_48h_inches": total("snowfall_rate_in_hr", 48),
            "snow_72h_inches": total("snowfall_rate_in_hr", 72),
            "snow_7d_total_inches": total("snowfall_rate_in_hr", 168),
            "model_raw_snow_48h_inches": total("model_snowfall_in_hr", 48),
            "model_raw_snow_7d_inches": total("model_snowfall_in_hr", 168),
            "liquid_48h_inches": round(sum(s["precip_in"] for s in steps[:48]), 2),
            "liquid_7d_inches": round(sum(s["precip_in"] for s in steps), 2),
            "slr_methods": {
                "cobb_adjusted": {"slr_48h": liquid_weighted("slr", 48), "slr_7d": liquid_weighted("slr", 168), "snow_48h": total("snowfall_rate_in_hr", 48), "snow_7d": total("snowfall_rate_in_hr", 168)},
                "kuchera": {"slr_48h": liquid_weighted("slr_kuchera", 48), "slr_7d": liquid_weighted("slr_kuchera", 168), "snow_48h": round(steps[min(47, len(steps) - 1)]["kuchera_cumulative_inches"], 1) if steps else 0,
                            "snow_7d": round(steps[-1]["kuchera_cumulative_inches"], 1) if steps else 0},
                "cobb_unadjusted": {"slr_48h": liquid_weighted("slr_cobb_raw", 48), "slr_7d": liquid_weighted("slr_cobb_raw", 168)},
                "fixed_10": {"slr_48h": 10.0, "slr_7d": 10.0, "snow_48h": round(liq48 * 10, 1), "snow_7d": round(liq7 * 10, 1)},
                "model_field_7to1": {"slr_48h": 7.0, "slr_7d": 7.0, "snow_48h": total("model_snowfall_in_hr", 48), "snow_7d": total("model_snowfall_in_hr", 168)},
            },
            "daily_forecast": daily,
            "hourly_timeline_48h": steps[:TIMELINE_HOURS],
            "_steps": steps,
        }

    @staticmethod
    def _ensemble_pop(ens: Dict[str, Any], n: int) -> Optional[List[int]]:
        """Hourly chance of >= 0.01 in of precipitation = share of ensemble members."""
        h = ens.get("hourly", {})
        keys = [k for k in h if k.startswith("precipitation")]
        if len(keys) < 5:
            return None
        out = []
        for i in range(n):
            vals = [h[k][i] for k in keys if h[k] and i < len(h[k]) and h[k][i] is not None]
            out.append(round(100 * sum(1 for v in vals if v >= 0.01) / len(vals)) if vals else 0)
        return out

    @staticmethod
    def _pct(vals: List[float], q: float) -> float:
        v = sorted(vals)
        if not v:
            return 0.0
        k = (len(v) - 1) * q
        lo, hi = int(math.floor(k)), int(math.ceil(k))
        return v[lo] + (v[hi] - v[lo]) * (k - lo)

    def _ensemble_summary(self, ens: Dict[str, Any], steps: List[Dict[str, Any]], daily: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Each member's liquid x this tier's hourly snow fraction x SLR, then percentiles."""
        h = ens.get("hourly", {})
        keys = [k for k in h if k.startswith("precipitation")]
        if not keys or not steps:
            return None
        factor = [s["snow_fraction"] * s["slr"] for s in steps]
        dates = [(datetime.fromisoformat(s["time"].replace("Z", "+00:00")) - timedelta(hours=8)).strftime("%Y-%m-%d") for s in steps]
        day_keys = [d["date"] for d in daily]
        members = []
        for k in keys:
            arr = h[k]
            if arr is None or sum(1 for x in arr[:len(steps)] if x is not None) < len(steps) * 0.5:
                continue
            snow = [(arr[i] or 0.0) * factor[i] if i < len(arr) else 0.0 for i in range(len(steps))]
            per_day = {d: 0.0 for d in day_keys}
            for i, v in enumerate(snow):
                if dates[i] in per_day:
                    per_day[dates[i]] += v
            members.append({"h24": sum(snow[:24]), "h48": sum(snow[:48]), "d7": sum(snow), "days": per_day,
                            "liq48": sum((arr[i] or 0.0) for i in range(min(48, len(arr))))})
        if len(members) < 5:
            return None

        def stats(vals):
            return {p: round(self._pct(vals, q), 1) for p, q in (("p10", .1), ("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))}

        out_daily, out_cum = [], []
        running = [0.0] * len(members)
        for d in day_keys:
            vals = [m["days"][d] for m in members]
            for i, v in enumerate(vals):
                running[i] += v
            st = stats(vals)
            st.update({"date": d,
                       "prob_6in": round(100 * sum(1 for v in vals if v >= 6) / len(vals)),
                       "prob_12in": round(100 * sum(1 for v in vals if v >= 12) / len(vals))})
            out_daily.append(st)
            cs = stats(running)
            cs["date"] = d
            out_cum.append(cs)
        return {
            "members": len(members),
            "models": ["GEFS (NOAA)", "ECMWF ENS", "ICON-EPS (DWD)"],
            "snow_24h": stats([m["h24"] for m in members]),
            "snow_48h": stats([m["h48"] for m in members]),
            "snow_7d": stats([m["d7"] for m in members]),
            "liquid_48h": {p: round(v, 2) for p, v in stats([m["liq48"] for m in members]).items()},
            "daily": out_daily,
            "cumulative_daily": out_cum,
        }

    @staticmethod
    def _daily_rollup(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group hourly steps into Pacific-time calendar days."""
        days: Dict[str, List[Dict[str, Any]]] = {}
        for s in steps:
            dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00")) - timedelta(hours=8)
            days.setdefault(dt.strftime("%Y-%m-%d"), []).append(s)
        out = []
        for d, ss in list(days.items())[:8]:
            liq = sum(x["precip_in"] for x in ss)
            out.append({
                "date": d,
                "hours": len(ss),
                "precip_in": round(liq, 2),
                "snow_share": round(sum(x["precip_in"] * x["snow_fraction"] for x in ss) / liq, 2) if liq > 0.01 else None,
                "ice_hours": sum(1 for x in ss if x["precip_phase"] == "ice"),
                "snowfall_inches": round(sum(x["snowfall_rate_in_hr"] for x in ss), 1),
                "temp_high_f": max(x["temp_f"] for x in ss),
                "temp_low_f": min(x["temp_f"] for x in ss),
                "max_gust_mph": max(x["gust_mph"] for x in ss),
            })
        return out

    # ------------------------------------------------------------------
    # Summary for the atmosphere cards (numbers + criteria, no prose)
    # ------------------------------------------------------------------
    def _summarize_sounding(self, profile: List[Dict[str, Any]], parsed: Dict[str, Any], tiers: Dict[str, Any]) -> Dict[str, Any]:
        window = profile[:24]
        summit_tl = parsed["summit"]["hourly_timeline_48h"][:24]
        base_tl = parsed["base"]["hourly_timeline_48h"][:24]
        wet_idx = [i for i, s in enumerate(summit_tl) if s["precip_in"] >= 0.01]
        basis = "precipitating hours in the next 24 h" if wet_idx else "all hours in the next 24 h (no precipitation forecast)"
        idx = wet_idx or list(range(len(window)))
        wp = [window[i] for i in idx if i < len(window)]

        def avg(vals):
            vals = [v for v in vals if v is not None]
            return sum(vals) / len(vals) if vals else None

        dgz_b, dgz_t = avg([p["dgz_base_ft"] for p in wp]), avg([p["dgz_top_ft"] for p in wp])
        dgz_pb, dgz_pt = avg([p["dgz_base_hpa"] for p in wp]), avg([p["dgz_top_hpa"] for p in wp])
        dgz_rh, dgz_rhi = avg([p["dgz_rh_pct"] for p in wp]), avg([p["dgz_rhi_pct"] for p in wp])
        dgz_lift = avg([p["dgz_lift_cm_s"] for p in wp])
        crosshair_hours = sum(1 for p in window if (p["dgz_rhi_pct"] or 0) >= 100 and (p["dgz_lift_cm_s"] or 0) >= 10)
        saturated = dgz_rhi is not None and dgz_rhi >= 100
        rising = (dgz_lift or 0) >= 10
        status = "SATURATED_RISING" if saturated and rising else ("SATURATED" if saturated else ("SUBSATURATED" if dgz_rhi is not None else "ABSENT"))

        fl = avg([p["freezing_level_ft"] for p in wp])
        wbz = avg([p["wet_bulb_zero_ft"] for p in wp])
        snow_lvl = avg([p["snow_level_ft"] for p in wp])
        base_ft = round(tiers["base"]["elevation_m"] * M_TO_FT)
        summit_ft = round(tiers["summit"]["elevation_m"] * M_TO_FT)
        if snow_lvl is None:
            risk = "LOW"
        elif base_ft > snow_lvl + 500:
            risk = "LOW"
        elif base_ft >= snow_lvl:
            risk = "MODERATE"
        else:
            risk = "HIGH"

        def snow_share(tl):
            wet = [s for s in tl if s["precip_in"] >= 0.01]
            if not wet:
                return None
            return round(100 * sum(s["snow_fraction"] * s["precip_in"] for s in wet) / sum(s["precip_in"] for s in wet))

        base_mr = avg([s["mixing_ratio_g_kg"] for s in base_tl]) or 0.0
        moist = "high (>= 5 g/kg)" if base_mr >= 5.0 else ("moderate (2.5-5 g/kg)" if base_mr >= 2.5 else "low (< 2.5 g/kg)")
        summit_winds = [s["wind_mph"] for s in summit_tl]
        dirs = [s["wind_dir_deg"] for s in summit_tl]
        mean_dir = round(math.degrees(math.atan2(sum(math.sin(math.radians(d)) for d in dirs),
                                                 sum(math.cos(math.radians(d)) for d in dirs))) % 360) if dirs else 0
        compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][round(mean_dir / 22.5) % 16]
        # Sierra crest is oriented ~NNW-SSE (about 340/160 deg); flow from 200-290 deg is within ~45 deg of perpendicular.
        oro = "upslope (within 45 deg of crest-normal)" if 200 <= mean_dir <= 290 else ("oblique" if 160 <= mean_dir <= 320 else "downslope / parallel")
        slr_avg = avg([summit_tl[i]["slr"] for i in idx if i < len(summit_tl)])

        return {
            "basis": basis,
            "dgz": {
                "base_elevation_ft": round(dgz_b) if dgz_b else None,
                "top_elevation_ft": round(dgz_t) if dgz_t else None,
                "base_pressure_hpa": round(dgz_pb) if dgz_pb else None,
                "top_pressure_hpa": round(dgz_pt) if dgz_pt else None,
                "thickness_ft": round(dgz_t - dgz_b) if (dgz_b and dgz_t) else None,
                "relative_humidity_pct": round(dgz_rh) if dgz_rh is not None else None,
                "relative_humidity_ice_pct": round(dgz_rhi) if dgz_rhi is not None else None,
                "lift_cm_s": round(dgz_lift, 1) if dgz_lift is not None else None,
                "saturated_and_rising_hours_24h": crosshair_hours,
                "status": status,
                "criteria": "saturated = RH w.r.t. ice >= 100%; rising = mean vertical velocity >= 10 cm/s",
                "avg_summit_slr": round(slr_avg, 1) if slr_avg else None,
            },
            "precipitation_phase_analysis": {
                "current_freezing_level_ft": round(fl) if fl else None,
                "wet_bulb_zero_ft": round(wbz) if wbz else None,
                "effective_snow_level_ft": round(snow_lvl) if snow_lvl else None,
                "base_village_elevation_ft": base_ft,
                "summit_elevation_ft": summit_ft,
                "base_rain_risk": risk,
                "base_rain_risk_criteria": "LOW: base > snow level + 500 ft; MODERATE: base within 500 ft above snow level; HIGH: base below snow level",
                "base_wet_bulb_f": round(avg([s["wet_bulb_f"] for s in base_tl]) or 0, 1),
                "snow_share_pct": {"summit": snow_share(summit_tl), "mid": snow_share(parsed["mid"]["hourly_timeline_48h"][:24]), "base": snow_share(base_tl)},
            },
            "moisture_and_dynamics": {
                "surface_mixing_ratio_g_kg": round(base_mr, 1),
                "moisture_category": moist,
                "summit_wind_avg_mph": round(avg(summit_winds) or 0),
                "peak_crest_gust_mph": round(max([s["gust_mph"] for s in summit_tl] or [0]), 1),
                "summit_wind_dir_deg": mean_dir,
                "summit_wind_dir": compass,
                "orographic_flow": oro,
            },
        }
