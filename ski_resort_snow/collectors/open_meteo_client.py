"""Open-Meteo collector: seven selectable models, model soundings and snow diagnostics.

Models (all via api.open-meteo.com):

  id            Open-Meteo model         sounding used                      hours
  nbm           ncep_nbm_conus           GFS (gfs_seamless) - NBM is surface-only here   ~270
  ecmwf_hres    ecmwf_ifs (9 km)         ECMWF IFS 0.25 deg (same model, surface-only here)  ~350
  aifs          ecmwf_aifs025_single     own                                ~360
  hrrr_gfs      gfs_seamless             own (HRRR 3 km ~0-47 h, then GFS)   384
  icon          icon_seamless            own, no vertical velocity          ~180
  ukmo          ukmo_seamless            own                                ~157
  gem           gem_seamless             own, no vertical velocity          ~240

For each model and tier: surface fields at the tier's coordinates and elevation
(one multi-model request per tier), a column at the summit point (one
multi-model request for the six sounding sources), and 168 hours of derived
fields. Ensembles (GEFS, ECMWF ENS, ICON-EPS) are fetched once per tier and
summarized with each model's snow fraction and SLR.

Elevation handling: surface fields are requested with elevation=nan, i.e. the
model's own grid-cell values, not Open-Meteo's statistical downscaling. That
downscaling moves 2 m temperature and dew point from the cell height to the
requested elevation with a fixed lapse of about 6.5 C/km (measured Nov 24,
2026: HRRR/GFS, ECMWF and GEM all shift by 6.5-6.7 C/km), which runs the wrong
way in an inversion. Instead, the cell's height is found on the model's own
column from its surface pressure, and temperature and dew point are moved by
the column's change between that height and the tier height
(T_tier = T_2m,cell + T_col(z_tier) - T_col(z_cell)). This keeps any inversion
the model has between the two heights. It still carries the model's own
near-surface layer (calm-night cooling at the cell), so the free-air
temperature at each tier height is reported alongside. Without a column for an
hour, the fixed 6.5 C/km is used and flagged. Precipitation and 10 m wind are
not elevation-adjusted.

Snow/liquid ratio (SLR):
  cobb (used)   Cobb & Waldstreicher (2005)-style: crystal-habit SLR of each
                ice-saturated layer above the tier, weighted by upward motion x
                thickness (thickness only for models without vertical velocity).
                No empirical adjustment.
  experimental  cobb x wind factor + near-freezing caps. Not calibrated; shown for
                comparison until fitted on multi-season observations.
  kuchera, fixed 10:1, and Open-Meteo's own snowfall field (fixed ~7:1).
"""

import json
import math
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

try:
    from . import precip_shift as ps
except ImportError:  # imported as a top-level module (collectors/ on sys.path)
    import precip_shift as ps

M_TO_FT = 3.28084
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200]
LEVEL_VARS = ["temperature", "relative_humidity", "geopotential_height", "vertical_velocity", "wind_speed", "wind_direction"]
TIMELINE_HOURS = 168
FORECAST_HOURS = 168
DEFAULT_MODEL = "nbm"
# Static blends shown as their own entries in the model selector (config/sources.json "blends" overrides).
# NBM is left out: it is already a blend that includes GFS and ECMWF.
DEFAULT_BLENDS = [{"id": "blend", "label": "Equal blend", "members": {"ecmwf_hres": 1, "aifs": 1, "hrrr_gfs": 1, "rrfs": 1, "icon": 1, "ukmo": 1},
                   "profile_from": "ecmwf_hres", "min_weight_share": 0.5}]
BLEND_MEAN_KEYS = {   # key -> rounding
    "precip_in": 3, "snowfall_rate_in_hr": 2, "model_snowfall_in_hr": 2, "slr_kuchera": 1, "slr_experimental": 1, "snow_fraction": 2,
    "precip_probability": 0, "temp_f": 1, "free_air_temp_f": 1, "wet_bulb_f": 1, "dew_point_f": 1, "relative_humidity_pct": 0,
    "mixing_ratio_g_kg": 2, "visibility_mi": 2, "cloud_cover_pct": 0, "wind_mph": 1, "gust_mph": 1, "model_10m_wind_mph": 1,
    "free_air_wind_mph": 1, "freezing_level_ft": 0, "snow_level_ft": 0, "wet_bulb_zero_ft": 0,
}

MODELS = [
    {"id": "nbm", "om": None, "label": "NBM", "provider": "NOAA/NWS (NOMADS, native GRIB2)", "grid": "2.5 km",
     "sounding": None, "sounding_label": "none (NBM has no vertical profile)", "meta": []},
    {"id": "ecmwf_hres", "om": "ecmwf_ifs", "label": "ECMWF HRES", "provider": "ECMWF", "grid": "9 km",
     "sounding": "ecmwf_ifs025", "sounding_label": "ECMWF IFS 0.25 deg", "meta": ["ecmwf_ifs"]},
    {"id": "aifs", "om": "ecmwf_aifs025_single", "label": "ECMWF AIFS", "provider": "ECMWF (machine-learning)", "grid": "0.25 deg",
     "sounding": "ecmwf_aifs025_single", "sounding_label": "own", "meta": ["ecmwf_aifs025_single"]},
    {"id": "hrrr_gfs", "om": "gfs_seamless", "label": "HRRR/GFS", "provider": "NOAA/NCEP", "grid": "3 km to ~47 h, then 0.25 deg",
     "sounding": "gfs_seamless", "sounding_label": "own", "meta": ["ncep_hrrr_conus", "ncep_gfs025"]},
    # RRFS: operational Nov 2026, 3 km, 84 h runs every 6 h; too new for a hindcast, so the hindcast scripts skip it
    {"id": "rrfs", "om": "ncep_rrfs_conus", "label": "RRFS", "provider": "NOAA/NCEP (Rapid Refresh Forecast System)", "grid": "3 km, to 84 h",
     "sounding": "ncep_rrfs_conus", "sounding_label": "own", "meta": ["ncep_rrfs_conus"], "hindcast": False},
    {"id": "icon", "om": "icon_seamless", "label": "ICON", "provider": "DWD (Germany)", "grid": "13 km",
     "sounding": "icon_seamless", "sounding_label": "own (no vertical velocity)", "meta": ["dwd_icon"]},
    {"id": "ukmo", "om": "ukmo_seamless", "label": "UKMO", "provider": "Met Office (UK)", "grid": "10 km",
     "sounding": "ukmo_seamless", "sounding_label": "own", "meta": ["ukmo_global_deterministic_10km"]},
    {"id": "gem", "om": "gem_seamless", "label": "GEM", "provider": "ECCC (Canada)", "grid": "10-15 km",
     "sounding": "gem_seamless", "sounding_label": "own (no vertical velocity)", "meta": ["cmc_gem_gdps"]},
]
SOUNDING_SOURCES = sorted({m["sounding"] for m in MODELS if m["sounding"]})
SURFACE_VARS = ["snowfall", "precipitation", "precipitation_probability", "temperature_2m", "dew_point_2m",
                "relative_humidity_2m", "wet_bulb_temperature_2m", "freezing_level_height", "cloud_cover",
                "visibility", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "surface_pressure"]
STD_LAPSE_C_PER_M = 0.0065   # Open-Meteo's own downscaling lapse; used only when a model column is missing
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
    """EXPERIMENTAL, not calibrated: -0.5 % per mph above 15 mph, floor 0.75.

    Direction of the effect is documented (stronger wind -> fragmented, packed crystals,
    lower SLR; e.g. Alcott & Steenburgh 2010), but these coefficients were only checked
    against one storm and are not used for the primary SLR. See TUNING_PLAN.md."""
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


def _highest_crossing(heights: List[float], values: List[float], target: float) -> Optional[float]:
    """Highest height (m) where `values` crosses `target`, scanning top-down.

    Freezing level and wet-bulb zero use the highest crossing: the top of any warm layer,
    above which the column stays below 0 C. The lowest crossing jumped on calm nights to
    levels below the model's terrain, where pressure-level values are extrapolated
    downward from the model's cold surface (HRRR/GFS at the Palisades summit, Nov 26-29,
    2026: 12,800 ft -> 6,500 ft -> 13,500 ft within hours)."""
    for i in range(len(heights) - 2, -1, -1):
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


def _height_at_pressure(levels: List[Dict[str, Any]], p_hpa: float) -> Optional[float]:
    """Height (m) of a pressure on the model column (linear in ln p, extrapolated at the ends)."""
    pts = sorted((math.log(lv["p"]), lv["z"]) for lv in levels if lv.get("p") and lv.get("z") is not None)
    if len(pts) < 2 or not p_hpa or p_hpa <= 0:
        return None
    lp = math.log(p_hpa)
    k = next((j for j in range(1, len(pts)) if pts[j][0] >= lp), len(pts) - 1)
    (l0, z0), (l1, z1) = pts[k - 1], pts[k]
    return z0 + (z1 - z0) * (lp - l0) / (l1 - l0) if l1 != l0 else z0


def _std_height_m(p_hpa: float) -> float:
    return 44330.8 * (1.0 - (p_hpa / 1013.25) ** 0.190263)


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

    def __init__(self, timeout_sec: int = 20, blends: Optional[List[Dict[str, Any]]] = None,
                 precip_correction: Optional[Dict[str, Any]] = None):
        self.blends = DEFAULT_BLENDS if blends is None else blends
        # elevation shift + residual multiplier for blends marked "precip_correction" (config/sources.json)
        self.precip_correction = precip_correction
        self._nbr_cache: Dict[Any, Any] = {}
        self.timeout_sec = timeout_sec
        self._meta_cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def fetch_resort_forecast(self, tiers: Dict[str, Dict[str, Any]], sensor: Optional[Dict[str, Any]] = None,
                              progress=None, nbm: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns {"status", "default": model output, "models": {id: model output}, ...}.

        tiers: {"base"|"mid"|"summit": {"lat", "lon", "elevation_m", "note"}}; sensor: same plus "id"."""
        say = progress or (lambda msg: None)
        labels = {"base": "Base", "mid": "Mid mountain", "summit": "Summit"}
        exposure = {"base": 0.0, "mid": 0.6, "summit": 1.0}
        om_ids = [m["om"] for m in MODELS if m["om"]]
        try:
            say("surface fields, 7 models x 3 elevations")
            surface = {k: self._query_surface(t["lat"], t["lon"], t["elevation_m"], om_ids) for k, t in tiers.items()}
            say("model soundings")
            summit = tiers["summit"]
            upper = self._query_upper_air(summit["lat"], summit["lon"], SOUNDING_SOURCES)
            profiles, has_w = {}, {}
            for src in SOUNDING_SOURCES:
                part = self._split(upper, src)
                profiles[src] = self._build_vertical_profile(part)
                has_w[src] = any(v is not None for v in (part["hourly"].get("vertical_velocity_700hPa") or []))

            say("ensembles")
            ensembles = {}
            for k, t in tiers.items():
                try:
                    ensembles[k] = self._query_ensemble(t["lat"], t["lon"], t["elevation_m"])
                except Exception:
                    ensembles[k] = None

            # neighborhoods for the precipitation correction (only when a blend uses it)
            nbr: Dict[str, Any] = {}
            want_corr = bool(self.precip_correction)   # corrected single models, and blends marked "precip_correction"
            if want_corr:
                say("model neighborhoods (precipitation correction)")
                nbr = self._fetch_neighborhoods(tiers, [m["om"] for m in MODELS if m["om"]])

            sensor_surface = None
            if sensor:
                try:
                    sensor_surface = self._query_surface(sensor["lat"], sensor["lon"], sensor["elevation_m"], ["gfs_seamless"])
                except Exception:
                    sensor_surface = None

            now = datetime.now(timezone.utc).isoformat()
            outputs, parsed_by_model, corrected_by_model, correction_info, corrected_outputs = {}, {}, {}, {}, {}
            for m in MODELS:
                say(f"model {m['label']}")
                if m["id"] == "nbm":
                    outputs["nbm"] = self._nbm_output(m, nbm, tiers, sensor, ensembles, labels, now)
                    continue
                prof = profiles.get(m["sounding"]) or []
                w_ok = has_w.get(m["sounding"], False)
                parts = {k: self._split(surface[k], m["om"]) for k in tiers}
                if not any(v is not None for v in parts["summit"]["hourly"].get("temperature_2m") or []):
                    outputs[m["id"]] = {"status": "error", "model": self._model_card(m, w_ok, None), "error_message": "no data for this location"}
                    continue
                parsed = {k: self._build_tier(parts[k], prof, labels[k], tiers[k]["elevation_m"], exposure[k], ensembles[k], w_ok) for k in tiers}
                parsed_by_model[m["id"]] = parsed
                if m["om"] in nbr:
                    try:
                        corr = self._corrected_tiers(m, parts, parsed, nbr[m["om"]], tiers, prof, labels, exposure, ensembles, w_ok)
                    except Exception as e:  # a failed correction only drops this member from the corrected blend
                        corr = (None, {"error": f"{type(e).__name__}: {e}"})
                    if corr[0]:
                        corrected_by_model[m["id"]] = corr[0]
                        try:
                            corrected_outputs[m["id"]] = self._corrected_output(m, corr[0], corr[1], prof, tiers, w_ok, now)
                        except Exception:
                            pass
                    correction_info[m["id"]] = corr[1]
                elif want_corr:
                    correction_info[m["id"]] = {"error": "neighborhood fetch failed"}
                out = self._assemble(m, parsed, prof, tiers, w_ok, now)
                if sensor and sensor_surface and m["id"] == "hrrr_gfs":
                    try:
                        s_tier = self._build_tier(self._split(sensor_surface, "gfs_seamless"), prof, sensor.get("id", "sensor"), sensor["elevation_m"], 0.6, None, w_ok)
                        out["sensor_point"] = {"id": sensor.get("id"), "lat": sensor["lat"], "lon": sensor["lon"],
                                               "elevation_ft": round(sensor["elevation_m"] * M_TO_FT),
                                               "hourly": [{k: x[k] for k in ("time", "precip_in", "snowfall_rate_in_hr", "slr", "slr_kuchera", "slr_experimental", "snow_fraction", "temp_f")}
                                                          for x in s_tier["_steps"][:48]],
                                               "liquid_48h_inches": s_tier["liquid_48h_inches"], "snow_48h_inches": s_tier["snow_48h_inches"],
                                               "slr_methods": s_tier["slr_methods"]}
                    except Exception:
                        pass
                outputs[m["id"]] = out

            # static blends (before the column details are dropped: the blend's profile panels use one of them)
            for bl in self.blends:
                try:
                    src_parsed = corrected_by_model if bl.get("precip_correction") else parsed_by_model
                    bo = self._blend_output(bl, outputs, src_parsed, profiles, has_w, tiers, labels, ensembles, now)
                    if bo and bl.get("precip_correction") and bo.get("status") == "success":
                        self._attach_correction(bo, correction_info, nbr)
                except Exception as e:  # a failed blend never takes the members down
                    bo = {"status": "error", "model": {"id": bl["id"], "label": bl.get("label", "Blend"), "provider": "blend", "grid": "",
                                                        "runs": [], "hours_available": None}, "error_message": f"{type(e).__name__}: {e}"}
                if bo:
                    outputs[bl["id"]] = bo
            # selector order: NBM, the blends, then the single models
            first = [k for k in ["nbm"] + [b["id"] for b in self.blends] if k in outputs]
            outputs = {k: outputs[k] for k in first + [k for k in outputs if k not in first]}

            for p in profiles.values():
                for x in p:
                    x.pop("_levels", None)
                    x.pop("_skewt", None)
                    x.pop("_ground_m", None)
            self._attach_profile(outputs.get("nbm"), outputs.get("hrrr_gfs"))

            def corr_summary(mid):
                s = (corrected_outputs.get(mid) or {}).get("summit_summary")
                return {"corrected_summary": {k: s.get(k) for k in ("liquid_48h", "liquid_7d", "snow_48h", "snow_7d", "covers_7d")}} if s else {}

            comparison = [{**o["model"], **(o.get("summit_summary") or {}), **corr_summary(mid),
                           **({"error": o.get("error_message")} if o.get("status") == "error" else {})}
                          for mid, o in outputs.items()]
            for o in list(outputs.values()) + list(corrected_outputs.values()):
                if o.get("status") == "success":
                    o["model_comparison"] = comparison
                    o["query_points"] = {k: {"lat": t["lat"], "lon": t["lon"], "elevation_ft": round(t["elevation_m"] * M_TO_FT), "note": t.get("note", "")}
                                         for k, t in tiers.items()}
            default = outputs.get(DEFAULT_MODEL)
            if not default or default.get("status") != "success":
                default = next((o for o in outputs.values() if o.get("status") == "success"), None)
            if not default:
                raise RuntimeError("no model returned data")
            return {"status": "success", "default_model": default["model"]["id"], "default": default, "models": outputs,
                    "corrected_models": corrected_outputs, "timestamp_utc": now}
        except Exception as e:
            return {
                "status": "error",
                "source": "Open-Meteo",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_message": f"{type(e).__name__}: {e}",
            }

    @staticmethod
    def _lead_weight(curve: List[List[float]], lead: int) -> float:
        """Piecewise-linear weight from [[lead_h, weight], ...] (held flat beyond the ends)."""
        pts = sorted(curve)
        if lead <= pts[0][0]:
            return float(pts[0][1])
        for (h0, w0), (h1, w1) in zip(pts, pts[1:]):
            if lead <= h1:
                return float(w0 + (w1 - w0) * (lead - h0) / max(1e-9, h1 - h0))
        return float(pts[-1][1])

    @staticmethod
    def _blend_steps(member_steps: Dict[str, List[Dict[str, Any]]], weights: Dict[str, float], min_weight: float,
                     lead_weights: Optional[Dict[str, List[List[float]]]] = None) -> List[Dict[str, Any]]:
        """Hourly weighted mean of the members present; stops when less than min_weight of them remain.

        Accumulations are averaged as hourly increments (a member that ends early can't make a total jump);
        the snow/liquid ratio is the ratio of the blended snow to the blended snow-fraction liquid, so
        snow = liquid x fraction x SLR still holds; wind direction is a speed-weighted vector mean."""
        idx = {mid: {s["time"]: s for s in steps} for mid, steps in member_steps.items()}
        times = sorted(set().union(*[set(d) for d in idx.values()])) if idx else []
        prev = {mid: {} for mid in idx}
        nominal = weights
        lw = lead_weights or {}
        cum = {"cumulative_snow_inches": 0.0, "model_cumulative_inches": 0.0, "kuchera_cumulative_inches": 0.0, "experimental_cumulative_inches": 0.0}
        out = []
        for lead, t in enumerate(times):
            present = {mid: idx[mid][t] for mid in idx if t in idx[mid]}
            if sum(nominal[mid] for mid in present) < min_weight:   # stop rule uses the nominal weights
                break
            weights = {mid: (OpenMeteoClient._lead_weight(lw[mid], lead) if mid in lw else nominal[mid]) for mid in idx}
            wsum = sum(weights[mid] for mid in present)

            def mean(key):
                vals = [(weights[mid], s[key]) for mid, s in present.items() if s.get(key) is not None]
                sw = sum(a for a, _ in vals)
                return sum(a * v for a, v in vals) / sw if sw else None

            x = {"time": t}
            for key, nd in BLEND_MEAN_KEYS.items():
                v = mean(key)
                x[key] = (round(v) if nd == 0 else round(v, nd)) if v is not None else None
            # accumulations: mean of each member's hourly increment
            for key in ("kuchera_cumulative_inches", "experimental_cumulative_inches"):
                inc = []
                for mid, s in present.items():
                    c = s.get(key)
                    if c is not None:
                        inc.append((weights[mid], c - prev[mid].get(key, 0.0)))
                        prev[mid][key] = c
                sw = sum(a for a, _ in inc)
                cum[key] += sum(a * v for a, v in inc) / sw if sw else 0.0
            cum["cumulative_snow_inches"] += x["snowfall_rate_in_hr"] or 0.0
            cum["model_cumulative_inches"] += x["model_snowfall_in_hr"] or 0.0
            for key, v in cum.items():
                x[key] = round(v, 2)
            for mid, s in present.items():   # each member's own running total, for the spread
                prev[mid]["snow"] = s.get("cumulative_snow_inches", prev[mid].get("snow", 0.0))
            # snow/liquid ratio consistent with the blended amounts
            num = sum(weights[mid] * (s.get("snowfall_rate_in_hr") or 0.0) for mid, s in present.items())
            den = sum(weights[mid] * (s.get("precip_in") or 0.0) * (s.get("snow_fraction") or 0.0) for mid, s in present.items())
            slr_mean = mean("slr")
            x["slr"] = round(num / den, 1) if den > 0.0005 else (round(slr_mean, 1) if slr_mean is not None else None)
            # wind direction
            u = sum(weights[mid] * (s.get("wind_mph") or 0) * math.sin(math.radians(s.get("wind_dir_deg") or 0)) for mid, s in present.items())
            v = sum(weights[mid] * (s.get("wind_mph") or 0) * math.cos(math.radians(s.get("wind_dir_deg") or 0)) for mid, s in present.items())
            x["wind_dir_deg"] = round(math.degrees(math.atan2(u, v)) % 360) % 360
            # phase from the blended snow fraction; ice when at least half the weight says ice
            frac, pop = x["snow_fraction"] or 0.0, x["precip_probability"] or 0
            ice_w = sum(weights[mid] for mid, s in present.items() if s.get("precip_phase") == "ice")
            if (x["precip_in"] or 0) < 0.005 and pop < 20:
                ph = "dry"
            elif ice_w >= wsum / 2:
                ph = "ice"
            else:
                ph = "snow" if frac >= 0.9 else ("rain" if frac <= 0.1 else "mix")
            x["precip_phase"] = ph
            x["precip_phase_label"] = {"dry": "None", "snow": "Snow", "mix": "Rain/snow", "rain": "Rain", "ice": "Sleet/freezing rain risk"}[ph]
            x["pop_source"] = "blend"
            x["chance_snow_pct"] = round(pop * frac)
            x["chance_rain_pct"] = round(pop * (1 - frac))
            if x["temp_f"] is not None and x["dew_point_f"] is not None:
                x["dew_point_depression_f"] = round(x["temp_f"] - x["dew_point_f"], 1)
            x["warm_layer_aloft"] = sum(weights[mid] for mid, s in present.items() if s.get("warm_layer_aloft")) >= wsum / 2
            # spread across the members present
            snows = [prev[mid]["snow"] for mid in present]
            temps = [s["temp_f"] for s in present.values() if s.get("temp_f") is not None]
            x["members"] = len(present)
            x["member_cum_snow_min"], x["member_cum_snow_max"] = round(min(snows), 2), round(max(snows), 2)
            x["member_temp_min"], x["member_temp_max"] = (round(min(temps), 1), round(max(temps), 1)) if temps else (None, None)
            out.append(x)
        return out

    def _blend_output(self, bl: Dict[str, Any], outputs: Dict[str, Any], parsed_by_model: Dict[str, Any], profiles: Dict[str, Any],
                      has_w: Dict[str, bool], tiers: Dict[str, Any], labels: Dict[str, str], ensembles: Dict[str, Any], now: str) -> Optional[Dict[str, Any]]:
        nominal = {mid: float(wt) for mid, wt in (bl.get("members") or {}).items() if wt and wt > 0}

        def member_steps(mid, k):
            # Open-Meteo models: the full parsed tier; NBM (read natively from NOAA): its elevation-adjusted timeline
            if mid in parsed_by_model:
                return parsed_by_model[mid][k]["_steps"]
            if bl.get("precip_correction"):
                return None   # corrected blends use only members with a correction
            return ((outputs.get(mid) or {}).get("elevation_timelines") or {}).get(k)

        w = {mid: wt for mid, wt in nominal.items() if (outputs.get(mid) or {}).get("status") == "success"
             and all(member_steps(mid, k) for k in tiers)}
        if len(w) < 2:
            return None
        min_w = float(bl.get("min_weight_share", 0.5)) * sum(nominal.values())
        parsed = {}
        lead_w = {mid: c for mid, c in (bl.get("lead_weights") or {}).items() if mid in w}
        for k in tiers:
            steps = self._blend_steps({mid: member_steps(mid, k) for mid in w}, w, min_w, lead_w)
            if not steps:
                return None
            p = self._summarize_tier(steps, labels[k], round(tiers[k]["elevation_m"] * M_TO_FT), ensembles.get(k), True)
            p["hourly_timeline_48h"] = steps[:TIMELINE_HOURS]
            parsed[k] = p
        src = next((x for x in MODELS if x["id"] == bl.get("profile_from", "ecmwf_hres")), None) or next(x for x in MODELS if x["id"] == "ecmwf_hres")
        prof = profiles.get(src["sounding"]) or []
        names = {x["id"]: x["label"] for x in MODELS}
        equal = len(set(w.values())) == 1 and not lead_w
        m = {"id": bl["id"], "label": bl.get("label", "Blend"), "om": None,
             "provider": f"{'Equal-weight mean' if equal else 'Weighted mean'} of {len(w)} models" + (f"; {bl['weights_note']}" if bl.get("weights_note") else ""),
             "grid": "mean of " + ", ".join(names.get(mid, mid) for mid in w), "sounding": src["sounding"],
             "sounding_label": f"{src['label']} column", "meta": []}
        out = self._assemble(m, parsed, prof, tiers, has_w.get(src["sounding"], False), now)
        out["model"]["runs"] = [{"model": names.get(mid, mid), **r} for mid in w for r in ((outputs[mid].get("model") or {}).get("runs") or [])[:1]]
        out["model"]["members"] = [{"id": mid, "label": names.get(mid, mid), "weight": round(wt / sum(w.values()), 3)} for mid, wt in w.items()]
        missing = [names.get(mid, mid) for mid in nominal if mid not in w]
        out["blend"] = {"members": out["model"]["members"], "missing": missing, "profile_from": src["label"],
                        "lead_weights": {names.get(mid, mid): c for mid, c in lead_w.items()} or None, "weights_note": bl.get("weights_note"),
                        "rule": f"hourly weighted mean of the members present; stops when under {round(100 * float(bl.get('min_weight_share', 0.5)))}% of the member weight remains"}
        out["column_runs"] = ((outputs.get(src["id"]) or {}).get("model") or {}).get("runs") or []   # the profile panels' model run
        out["primary_model"]["label"] = f"{m['label']} ({len(w)} models)" if len(w) > 2 else f"{m['label']} ({' + '.join(names.get(mid, mid) for mid in w)})"
        out["source"] = f"Blend of {len(w)} Open-Meteo models"
        out["methodology"]["blend"] = out["blend"]["rule"]
        return out

    # ------------------------------------------------------------------
    # Precipitation correction: elevation shift from each model's neighborhood, then a residual multiplier
    # ------------------------------------------------------------------
    @staticmethod
    def _neighborhood_points(tiers: Dict[str, Any], step_deg: float) -> List[List[float]]:
        """3x3 points one grid step apart around the middle of the resort's tiers (as in the hindcast)."""
        lat0 = sum(t["lat"] for t in tiers.values()) / len(tiers)
        lon0 = sum(t["lon"] for t in tiers.values()) / len(tiers)
        dlon = step_deg / math.cos(math.radians(lat0))
        return [[round(lat0 + i * step_deg, 4), round(lon0 + j * dlon, 4)] for i in (-1, 0, 1) for j in (-1, 0, 1)]

    def _query_points(self, points: List[List[float]], om_id: str) -> List[Dict[str, Any]]:
        """Hourly precipitation at several points for one model, each at its own grid cell (elevation=nan)."""
        d = self._get(self.BASE_URL, {
            "latitude": ",".join(f"{a:.4f}" for a, _ in points), "longitude": ",".join(f"{b:.4f}" for _, b in points),
            "elevation": ",".join("nan" for _ in points), "hourly": "precipitation", "models": om_id,
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT", "precipitation_unit": "inch",
        }, timeout=self.timeout_sec * 2)
        return d if isinstance(d, list) else [d]

    def _fetch_neighborhoods(self, tiers: Dict[str, Any], om_ids: List[str]) -> Dict[str, Any]:
        """{om_id: [cell {lat, lon, z, lake, series}]}, one entry per distinct cell; models that fail are left out."""
        out = {}
        for om_id in om_ids:
            step = ps.GRID_STEP_DEG.get(om_id)
            if not step:
                continue
            pts = self._neighborhood_points(tiers, step)
            c_lat, c_lon = pts[4]
            dlon = step / math.cos(math.radians(c_lat))
            now = datetime.now(timezone.utc)
            # a neighborhood fetched for another resort in this refresh is reused when this resort's middle is
            # within half a grid step of its middle (Palisades and Alpine share every model but HRRR/GFS)
            hit = next((e for e in self._nbr_cache.get(om_id, []) if (now - e[0]).total_seconds() < 900
                        and abs(e[1] - c_lat) <= step / 2 and abs(e[2] - c_lon) <= dlon / 2), None)
            if hit:
                resp = hit[3]
            else:
                try:
                    resp = self._query_points(pts, om_id)
                except Exception:
                    continue
                self._nbr_cache.setdefault(om_id, []).append((now, c_lat, c_lon, resp))
            cells = {}
            for r in resp:
                if r.get("latitude") is None:
                    continue
                key = (round(r["latitude"], 3), round(r["longitude"], 3))
                if key in cells:
                    continue
                z, lake = ps.cell_height_ft(r.get("elevation"))
                h = r.get("hourly") or {}
                cells[key] = {"lat": r["latitude"], "lon": r["longitude"], "z": z, "lake": lake,
                              "series": dict(zip(h.get("time", []), h.get("precipitation", [])))}
            if cells:
                out[om_id] = list(cells.values())
        return out

    def _correction_residual(self, mid: str) -> float:
        pc = self.precip_correction or {}
        lo, hi = pc.get("residual_bounds", [0.5, 2.0])
        r = float((pc.get("residual") or {}).get(mid, 1.0))
        return max(lo, min(hi, r))

    @staticmethod
    def corrected_precip(times: List[str], raw: List[Optional[float]], cells: List[Dict[str, Any]], lat: float, lon: float,
                         z_ft: float, residual: float) -> Tuple[List[Optional[float]], Dict[str, Any]]:
        """Hourly precipitation at a tier: elevation line from the neighborhood cells, times the residual.

        Falls back to the tier's own cell (still times the residual) when the cells can't support a line."""
        weights, info = ps.line_weights(cells, lat, lon, z_ft)
        info["lake_cells"] = sum(1 for c in cells if c.get("lake"))
        if weights:
            shifted = ps.shift_hourly([[c["series"].get(t) for t in times] for c in cells], weights)
        else:
            shifted = [None] * len(times)
            info["fallback"] = "own cell: " + info.get("reason", "no line")
        out = []
        for i in range(len(times)):
            base = shifted[i] if shifted[i] is not None else (raw[i] if i < len(raw) else None)
            out.append(None if base is None else round(base * residual, 4))
        return out, info

    def _corrected_tiers(self, m: Dict[str, Any], parts: Dict[str, Any], parsed: Dict[str, Any], cells: List[Dict[str, Any]],
                         tiers: Dict[str, Any], prof: List[Dict[str, Any]], labels: Dict[str, str], exposure: Dict[str, float],
                         ensembles: Dict[str, Any], w_ok: bool):
        """One model's tiers rebuilt with corrected precipitation (snow follows from liquid x fraction x SLR)."""
        res = self._correction_residual(m["id"])
        fitted = m["id"] in ((self.precip_correction or {}).get("residual") or {})
        out, info = {}, {"residual": round(res, 3), "residual_fitted": fitted, "cells": len(cells), "tiers": {}}
        for k, t in tiers.items():
            h = parts[k]["hourly"]
            times, raw = h.get("time", []), h.get("precipitation") or []
            z_ft = t["elevation_m"] * M_TO_FT
            corr, ti = self.corrected_precip(times, raw, cells, t["lat"], t["lon"], z_ft, res)
            snow = h.get("snowfall") or []
            scaled_snow = [None if s is None else (s * (c / r) if (r or 0) > 0.001 and c is not None else s)
                           for s, r, c in zip(snow, raw + [None] * (len(snow) - len(raw)), corr + [None] * (len(snow) - len(corr)))]
            part = {"hourly": {**h, "precipitation": corr, "snowfall": scaled_snow}, "hourly_units": parts[k].get("hourly_units", {})}
            out[k] = self._build_tier(part, prof, labels[k], t["elevation_m"], exposure[k], ensembles.get(k), w_ok)
            p_raw, p_cor = parsed[k], out[k]
            ti.update({"liquid_48h_raw": p_raw["liquid_48h_inches"], "liquid_48h": p_cor["liquid_48h_inches"],
                       "liquid_7d_raw": p_raw["liquid_7d_inches"], "liquid_7d": p_cor["liquid_7d_inches"],
                       "snow_48h_raw": p_raw["snow_48h_inches"], "snow_48h": p_cor["snow_48h_inches"],
                       "snow_7d_raw": p_raw["snow_7d_total_inches"], "snow_7d": p_cor["snow_7d_total_inches"],
                       "tier_ft": round(z_ft)})
            info["tiers"][k] = ti
        return out, info

    def _corrected_output(self, m: Dict[str, Any], parsed_c: Dict[str, Any], info: Dict[str, Any], prof: List[Dict[str, Any]],
                          tiers: Dict[str, Any], w_ok: bool, now: str) -> Dict[str, Any]:
        """A single model's full output with its precipitation corrected (same id; shown by the page's toggle)."""
        out = self._assemble({**m, "label": f"{m['label']} (corrected)"}, parsed_c, prof, tiers, w_ok, now)
        pc = self.precip_correction or {}
        out["model"]["corrected"] = True
        out["primary_model"]["label"] = out["primary_model"]["label"].replace(" (corrected) (", " (") + ", precipitation corrected"
        out["source"] = f"Open-Meteo: {m['label']}, precipitation corrected"
        out["precip_correction"] = {"method": pc.get("method"), "fitted": pc.get("fitted"),
                                    "members": {m["id"]: {"label": m["label"], **info}}, "uncorrected": []}
        out["methodology"]["precip_correction"] = pc.get("method")
        return out

    def _attach_correction(self, bo: Dict[str, Any], correction_info: Dict[str, Any], nbr: Dict[str, Any]) -> None:
        pc = self.precip_correction or {}
        names = {x["id"]: x["label"] for x in MODELS}
        used = [x["id"] for x in (bo.get("blend") or {}).get("members", [])]
        bo["blend"]["correction"] = {
            "method": pc.get("method"), "fitted": pc.get("fitted"),
            "members": {mid: {"label": names.get(mid, mid), **correction_info.get(mid, {})} for mid in used},
            "uncorrected": [names.get(mid, mid) for mid, inf in correction_info.items() if inf.get("error")],
        }
        bo["methodology"]["precip_correction"] = pc.get("method")

    @staticmethod
    def _attach_profile(nbm_out: Optional[Dict[str, Any]], src: Optional[Dict[str, Any]], src_label: str = "HRRR/GFS") -> None:
        """NBM has no vertical profile. Give its profile panels the HRRR/GFS column (freezing level,
        wet-bulb zero, DGZ, skew-T), keep NBM's own snow level, and label the source everywhere."""
        if not nbm_out or nbm_out.get("status") != "success" or not src or src.get("status") != "success":
            return
        sl_by_time = {x["time"]: x.get("snow_level_ft") for x in nbm_out.get("hourly_timeline", [])}
        prof = []
        for x in src.get("vertical_profile", []):
            y = dict(x)
            y["snow_level_ft"] = sl_by_time.get(x["time"])
            y["snow_level_source"] = "NBM"
            prof.append(y)
        nbm_out["vertical_profile"] = prof
        nbm_out["sounding_hourly"] = src.get("sounding_hourly", [])
        nbm_out["profile_model"] = {"id": "hrrr_gfs", "label": src_label, "runs": (src.get("model") or {}).get("runs") or [],
                                    "note": f"NBM has no vertical profile; freezing level, wet-bulb zero, DGZ and the skew-T come from {src_label}. Snow level is NBM's."}
        snd = dict(src.get("atmospheric_sounding") or {})
        if snd:
            snd["available"] = True
            snd["profile_model"] = src_label
            ph = dict(snd.get("precipitation_phase_analysis") or {})
            sls = [v for v in (sl_by_time.get(x["time"]) for x in src.get("vertical_profile", [])[:24]) if v is not None]
            if sls:
                sl = sum(sls) / len(sls)
                base = ph.get("base_village_elevation_ft")
                ph["effective_snow_level_ft"] = round(sl)
                ph["snow_level_source"] = "NBM"
                if base is not None:
                    ph["base_rain_risk"] = "LOW" if base > sl + 500 else ("MODERATE" if base >= sl else "HIGH")
            snd["precipitation_phase_analysis"] = ph
            own = (nbm_out.get("atmospheric_sounding") or {}).get("moisture_and_dynamics")
            if own:
                snd["moisture_and_dynamics"] = own
            nbm_out["atmospheric_sounding"] = snd
        # per-tier free-air temperature and the column levels on the timelines, labeled by source
        for tier, tl in (nbm_out.get("elevation_timelines") or {}).items():
            src_tl = {x["time"]: x for x in (src.get("elevation_timelines") or {}).get(tier, [])}
            prof_t = {x["time"]: x for x in prof}
            for x in tl:
                o, pr = src_tl.get(x["time"]), prof_t.get(x["time"])
                if o:
                    x["free_air_temp_f"] = o.get("free_air_temp_f")
                if pr:
                    x["freezing_level_ft"] = pr.get("freezing_level_ft")
                    x["wet_bulb_zero_ft"] = pr.get("wet_bulb_zero_ft")
                x["column_source"] = src_label
        fl = [x.get("freezing_level_ft") for x in prof[:24] if x.get("freezing_level_ft") is not None]
        nbm_out["avg_freezing_level_ft"] = round(sum(fl) / len(fl)) if fl else None

    @staticmethod
    def _surface_moisture(base_tl: List[Dict[str, Any]], summit_tl: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Base mixing ratio and summit wind from surface fields only (used when a model has no vertical profile)."""
        mrs = [x["mixing_ratio_g_kg"] for x in base_tl if x.get("mixing_ratio_g_kg") is not None]
        base_mr = sum(mrs) / len(mrs) if mrs else None
        winds = [x["wind_mph"] for x in summit_tl if x.get("wind_mph") is not None]
        dirs = [x["wind_dir_deg"] for x in summit_tl if x.get("wind_dir_deg") is not None]
        if not dirs:
            return {"surface_mixing_ratio_g_kg": round(base_mr, 1) if base_mr is not None else None}
        mean_dir = round(math.degrees(math.atan2(sum(math.sin(math.radians(d)) for d in dirs),
                                                 sum(math.cos(math.radians(d)) for d in dirs))) % 360)
        compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][round(mean_dir / 22.5) % 16]
        oro = "upslope (within 45 deg of crest-normal)" if 200 <= mean_dir <= 290 else ("oblique" if 160 <= mean_dir <= 320 else "downslope / parallel")
        moist = None if base_mr is None else ("high (>= 5 g/kg)" if base_mr >= 5.0 else ("moderate (2.5-5 g/kg)" if base_mr >= 2.5 else "low (< 2.5 g/kg)"))
        return {"surface_mixing_ratio_g_kg": round(base_mr, 1) if base_mr is not None else None, "moisture_category": moist,
                "summit_wind_avg_mph": round(sum(winds) / len(winds)) if winds else None, "summit_wind_dir_deg": mean_dir,
                "summit_wind_dir": compass, "orographic_flow": oro}

    def _nbm_output(self, m: Dict[str, Any], nbm: Optional[Dict[str, Any]], tiers: Dict[str, Any], sensor: Optional[Dict[str, Any]],
                    ensembles: Dict[str, Any], labels: Dict[str, str], now: str) -> Dict[str, Any]:
        """NBM from NOAA's own GRIB2 fields; no other model is involved."""
        try:
            from .nbm_client import NBMClient
        except ImportError:
            from nbm_client import NBMClient
        card = {"id": "nbm", "label": "NBM", "provider": m["provider"], "grid": m["grid"], "open_meteo_model": None,
                "sounding_source": None, "sounding_label": m["sounding_label"], "sounding_has_vertical_velocity": False,
                "runs": [], "hours_available": None}
        if not nbm or nbm.get("status") != "success":
            return {"status": "error", "model": card, "error_message": (nbm or {}).get("error_message", "NBM not fetched")}
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        try:
            from .nbm_downscale import Downscaler
        except ImportError:
            from nbm_downscale import Downscaler
        ds = Downscaler(nbm, nbm.get("terrain") or {}, NBMClient.to_steps) if nbm.get("box") else None
        ds = ds if ds and ds.ok else None
        parsed, points, adjust = {}, {}, {}
        for k, t in tiers.items():
            pt = nbm["points"].get(k) or {}
            elev_ft = round(t["elevation_m"] * M_TO_FT)
            if ds:
                steps, adjust[k] = ds.adjust(t["lat"], t["lon"], elev_ft, start)
            else:
                steps = NBMClient.to_steps(nbm["cycle_utc"], pt.get("rows", {}), elev_ft, start)
            p_hpa = std_pressure_hpa(t["elevation_m"])
            for x in steps:   # wet bulb and mixing ratio from NBM's own T and Td (psychrometric; our calculation)
                if x["temp_f"] is not None and x["dew_point_f"] is not None:
                    x["wet_bulb_f"] = round(c_to_f(wet_bulb_psychro_c(f_to_c(x["temp_f"]), f_to_c(x["dew_point_f"]), p_hpa)), 1)
                    x["mixing_ratio_g_kg"] = round(mixing_ratio_g_kg(f_to_c(x["dew_point_f"]), p_hpa), 2)
                else:
                    x["wet_bulb_f"] = x["mixing_ratio_g_kg"] = None
                x["chance_snow_pct"] = round((x["precip_probability"] or 0) * (x["snow_fraction"] or 0))
                x["chance_rain_pct"] = round((x["precip_probability"] or 0) * (1 - (x["snow_fraction"] or 0)))
            parsed[k] = self._summarize_tier(steps, labels[k], round(t["elevation_m"] * M_TO_FT), ensembles.get(k), False, nbm=True)
            parsed[k]["hourly_timeline_48h"] = steps[:TIMELINE_HOURS]
            points[k] = {"grid_lat": pt.get("grid_lat"), "grid_lon": pt.get("grid_lon"),
                         **({"grid_elevation_ft": adjust[k]["grid_elevation_ft"]} if k in adjust else {})}
        summit = parsed["summit"]
        s_tl = summit["hourly_timeline_48h"]
        card.update({"runs": [{"model": "NBM v4 CONUS", "run_init_utc": nbm["cycle_utc"], "run_available_utc": nbm.get("fetched_at_utc")}],
                     "hours_available": summit["hours_available"]})
        out = {
            "status": "success", "source": "NOAA NBM (NOMADS)", "timestamp_utc": now, "fetched_at_utc": nbm.get("fetched_at_utc", now),
            "model": card, "primary_model": {"id": "nbm", "label": "NBM (2.5 km)", "runs": card["runs"]},
            "nbm_grid_points": points,
            "nbm_elevation_adjustment": adjust or None,
            "summit_summary": {"liquid_24h": summit["liquid_24h_inches"], "liquid_48h": summit["liquid_48h_inches"],
                               "liquid_7d": summit["liquid_7d_inches"], "snow_48h": summit["snow_48h_inches"],
                               "snow_7d": summit["snow_7d_total_inches"], "covers_48h": summit["hours_available"] >= 47,
                               "covers_7d": summit["hours_available"] >= 160, "hours_available": summit["hours_available"],
                               "peak_gust_48h": round(max([x["gust_mph"] or 0 for x in s_tl[:48]] or [0.0]), 1),
                               "cell_elevation_ft": (adjust.get("summit") or {}).get("grid_elevation_ft")},
            "base": {k: v for k, v in parsed["base"].items() if k not in ("hourly_timeline_48h", "_steps")},
            "mid": {k: v for k, v in parsed["mid"].items() if k not in ("hourly_timeline_48h", "_steps")},
            "summit": {k: v for k, v in summit.items() if k not in ("hourly_timeline_48h", "_steps")},
            "base_48h_inches": parsed["base"]["snow_48h_inches"], "mid_48h_inches": parsed["mid"]["snow_48h_inches"],
            "summit_48h_inches": summit["snow_48h_inches"], "summit_7d_total_inches": summit["snow_7d_total_inches"],
            "peak_gust_summit_mph": round(max([x["gust_mph"] or 0 for x in s_tl[:48]] or [0.0]), 1),
            "avg_freezing_level_ft": None,
            "elevation_timelines": {k: parsed[k]["hourly_timeline_48h"] for k in parsed},
            "hourly_timeline": s_tl,
            "vertical_profile": [], "sounding_hourly": [],
            "atmospheric_sounding": {"available": False, "reason": "NBM has no vertical profile; select another model for the sounding panels.",
                                     "moisture_and_dynamics": self._surface_moisture(parsed["base"]["hourly_timeline_48h"][:24], s_tl[:24])},
            "methodology": {"snowfall": "NBM's own snowfall (ASNOW), snow/liquid ratio (SNOWLR) and snow level (SNOWLVL), nearest 2.5 km grid point",
                            "sounding": "none", "hours": "hourly to 48 h, then 6 h NBM values (accumulations spread over 6 h, other fields interpolated)"},
        }
        if sensor and nbm["points"].get("sensor"):
            sp = nbm["points"]["sensor"]
            s_elev = round(sensor["elevation_m"] * M_TO_FT)
            s_diag = None
            if ds:
                st, s_diag = ds.adjust(sensor["lat"], sensor["lon"], s_elev, start)
            else:
                st = NBMClient.to_steps(nbm["cycle_utc"], sp.get("rows", {}), s_elev, start)
            out["sensor_point"] = {"id": sensor.get("id"), "lat": sensor["lat"], "lon": sensor["lon"], "model": "NBM",
                                   "elevation_ft": s_elev, "elevation_adjustment": s_diag,
                                   "hourly": [{k: x.get(k) for k in ("time", "precip_in", "snowfall_rate_in_hr", "slr", "snow_fraction", "temp_f")} for x in st[:48]]}
        return out

    def _model_card(self, m: Dict[str, Any], has_w: bool, hours: Optional[int]) -> Dict[str, Any]:
        runs = [self._model_meta(x) for x in m["meta"]]
        for r in runs:
            try:
                if r.get("run_init_utc") and (datetime.now(timezone.utc) - datetime.fromisoformat(r["run_init_utc"])).days >= 3:
                    r["run_init_utc"] = r["run_available_utc"] = None
                    r["run_note"] = "run time not reported by Open-Meteo"
            except Exception:
                pass
        return {"id": m["id"], "label": m["label"], "provider": m["provider"], "grid": m["grid"], "open_meteo_model": m["om"],
                "sounding_source": m["sounding"], "sounding_label": m["sounding_label"], "sounding_has_vertical_velocity": has_w,
                "runs": runs, "hours_available": hours}

    def _assemble(self, m: Dict[str, Any], parsed: Dict[str, Any], prof: List[Dict[str, Any]], tiers: Dict[str, Any],
                  has_w: bool, now: str) -> Dict[str, Any]:
        summit = parsed["summit"]
        s_tl = summit["hourly_timeline_48h"]
        fl = [p["freezing_level_ft"] for p in prof[:48] if p.get("freezing_level_ft")]
        sounding = self._summarize_sounding(prof, parsed, tiers)
        sounding_hourly = [{"time": p["time"], "levels": p["_skewt"],
                            "ground_m": round(p["_ground_m"]) if p.get("_ground_m") is not None else None}
                           for p in prof[:TIMELINE_HOURS]] if prof else []
        card = self._model_card(m, has_w, summit["hours_available"])
        out = {
            "status": "success",
            "source": f"Open-Meteo: {m['label']}",
            "timestamp_utc": now, "fetched_at_utc": now,
            "model": card,
            "primary_model": {"id": m["id"], "label": f"{m['label']} ({m['grid']})" + ("" if m["sounding_label"].startswith("own") else f" + {m['sounding_label']} sounding"),
                              "runs": card["runs"]},
            "summit_summary": {"liquid_24h": summit["liquid_24h_inches"], "liquid_48h": summit["liquid_48h_inches"],
                               "liquid_7d": summit["liquid_7d_inches"], "snow_48h": summit["snow_48h_inches"],
                               "snow_7d": summit["snow_7d_total_inches"], "covers_48h": summit["hours_available"] >= 47,
                               "covers_7d": summit["hours_available"] >= 160, "hours_available": summit["hours_available"],
                               "peak_gust_48h": round(max([x["gust_mph"] for x in s_tl[:48]] or [0.0]), 1),
                               "cell_elevation_ft": (summit.get("elevation_adjustment") or {}).get("cell_elevation_ft")},
            "elevation_adjustment": {k: parsed[k].get("elevation_adjustment") for k in parsed},
            "base": {k: v for k, v in parsed["base"].items() if k not in ("hourly_timeline_48h", "_steps")},
            "mid": {k: v for k, v in parsed["mid"].items() if k not in ("hourly_timeline_48h", "_steps")},
            "summit": {k: v for k, v in summit.items() if k not in ("hourly_timeline_48h", "_steps")},
            "base_48h_inches": parsed["base"]["snow_48h_inches"],
            "mid_48h_inches": parsed["mid"]["snow_48h_inches"],
            "summit_48h_inches": summit["snow_48h_inches"],
            "summit_7d_total_inches": summit["snow_7d_total_inches"],
            "peak_gust_summit_mph": round(max([x["gust_mph"] for x in s_tl[:48]] or [0.0]), 1),
            "avg_freezing_level_ft": round(sum(fl) / len(fl)) if fl else None,
            "elevation_timelines": {k: parsed[k]["hourly_timeline_48h"] for k in parsed},
            "hourly_timeline": s_tl,
            "vertical_profile": [{k: v for k, v in p.items() if not k.startswith("_")} for p in prof[:TIMELINE_HOURS]],
            "sounding_hourly": sounding_hourly,
            "atmospheric_sounding": sounding,
            "methodology": {
                "snowfall": "liquid x snow fraction (wet-bulb zero height) x SLR (Cobb-style habit x lift; no empirical adjustment)",
                "sounding": f"{m['sounding_label']} column at the summit point" if not m["sounding_label"].startswith("own") else "model's own column at the summit point",
                "slr_alternates": "experimental wind/near-freezing adjustment (uncalibrated), Kuchera, fixed 10:1, Open-Meteo snowfall field (~7:1)",
            },
        }
        return out

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

    @staticmethod
    def _split(resp: Dict[str, Any], om_id: str) -> Dict[str, Any]:
        """One model's fields from a multi-model response (keys are suffixed with _<model>)."""
        h, u = resp.get("hourly", {}), resp.get("hourly_units", {})
        suf = f"_{om_id}"
        out = {"time": h.get("time", [])}
        units = {}
        for k, v in h.items():
            if k.endswith(suf):
                out[k[: -len(suf)]] = v
                units[k[: -len(suf)]] = u.get(k)
        return {"hourly": out, "hourly_units": units}

    def _query_surface(self, lat: float, lon: float, elevation_m: int, om_ids: List[str]) -> Dict[str, Any]:
        return self._get(self.BASE_URL, {
            # elevation=nan: the model's own grid-cell values; _build_tier moves them to elevation_m
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": "nan",
            "hourly": ",".join(SURFACE_VARS), "models": ",".join(om_ids),
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT",
            "precipitation_unit": "inch", "wind_speed_unit": "mph", "temperature_unit": "fahrenheit",
        }, timeout=self.timeout_sec * 2)

    def _query_upper_air(self, lat: float, lon: float, om_ids: List[str]) -> Dict[str, Any]:
        hourly = [f"{v}_{p}hPa" for p in PRESSURE_LEVELS for v in LEVEL_VARS] + ["surface_pressure"]   # model ground
        return self._get(self.BASE_URL, {
            # elevation=nan: surface_pressure is the model's own ground, not downscaled to the point's height
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": "nan",
            "hourly": ",".join(hourly), "models": ",".join(om_ids),
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0", "timezone": "GMT",
            "wind_speed_unit": "mph",   # heights stay in meters, temperatures in C
        }, timeout=self.timeout_sec * 4)

    def _query_ensemble(self, lat: float, lon: float, elevation_m: int) -> Dict[str, Any]:
        return self._get(self.ENSEMBLE_URL, {
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": str(elevation_m),
            "hourly": "precipitation", "models": ENSEMBLE_MODELS,
            "forecast_hours": str(FORECAST_HOURS), "past_hours": "0",
            "timezone": "GMT", "precipitation_unit": "inch",
        }, timeout=self.timeout_sec * 2)

    def _model_meta(self, meta_id: str) -> Dict[str, Any]:
        if meta_id in self._meta_cache:
            return dict(self._meta_cache[meta_id])
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
        return dict(out)

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
            # the model's ground at the column point: levels below it are extrapolations, not air
            p_sfc = _val(uh.get("surface_pressure"), i)
            ground_m = _height_at_pressure(levels, p_sfc) if (levels and p_sfc) else None
            air = [lv for lv in levels if ground_m is None or lv["z"] >= ground_m - 1.0]
            za = [lv["z"] for lv in air]

            wbz_m = _highest_crossing(zs, [lv["tw"] for lv in levels], 0.0)
            fzl_m = _highest_crossing(zs, [lv["t"] for lv in levels], 0.0)
            column_cold = bool(levels) and levels[0]["tw"] <= 0 and wbz_m is None

            dgz_bot = _interp_height_for_value(za, [lv["t"] for lv in air], -12.0)
            dgz_top = _interp_height_for_value(za, [lv["t"] for lv in air], -18.0)
            dgz = {}
            if dgz_bot is not None and dgz_top is not None and dgz_top > dgz_bot:
                samples = (dgz_bot, (dgz_bot + dgz_top) / 2, dgz_top)
                avg = lambda key: sum(_interp_at_height(za, [lv[key] for lv in air], h) for h in samples) / 3
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
                "ground_ft": ft(ground_m),
                "freezing_level_below_ground": bool(fzl_m is not None and ground_m is not None and fzl_m < ground_m),
                "wbz_below_ground": bool(wbz_m is not None and ground_m is not None and wbz_m < ground_m),
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
                "_ground_m": ground_m,
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
                    exposure: float = 1.0, ensemble: Optional[Dict[str, Any]] = None, has_w: bool = True) -> Dict[str, Any]:
        """One tier's hourly timeline for one model.

        data["hourly"] holds that model's surface fields; profile is the sounding used
        (the model's own, or its companion for surface-only models)."""
        h = data.get("hourly", {})
        units = data.get("hourly_units", {})
        times = h.get("time", [])
        # Only hours where the model actually has data (shorter models end early; never fill gaps)
        valid = [i for i in range(len(times)) if _val(h.get("temperature_2m"), i) is not None]
        n = min(FORECAST_HOURS, (max(valid) + 1) if valid else 0)
        elev_ft = round(elevation_m * M_TO_FT)
        p_hpa = std_pressure_hpa(elevation_m)
        ens_pop = self._ensemble_pop(ensemble, n) if ensemble else None
        vis_unit = units.get("visibility", "m")
        vis_to_mi = 1 / 5280.0 if vis_unit in ("ft", "feet") else 1 / 1609.344

        steps = []
        cum = cum_model = cum_k = cum_10 = cum_exp = 0.0
        for i in range(n):
            t = times[i]
            prof = profile[i] if i < len(profile) else {}
            levels = prof.get("_levels", [])
            ground = prof.get("_ground_m")
            above = [lv for lv in levels if lv["z"] >= elevation_m and (ground is None or lv["z"] >= ground - 1.0)]

            precip = _val(h.get("precipitation"), i, 0.0)
            model_snow = _val(h.get("snowfall"), i, 0.0)
            model_pop = _val(h.get("precipitation_probability"), i)
            pop = ens_pop[i] if ens_pop else (int(model_pop) if model_pop is not None else (100 if precip >= 0.01 else 0))
            temp_f = _val(h.get("temperature_2m"), i)
            dew_f = _val(h.get("dew_point_2m"), i)
            rh = _val(h.get("relative_humidity_2m"), i)
            if dew_f is None and rh is not None:
                dew_f = c_to_f(dewpoint_c(f_to_c(temp_f), rh))
            # grid cell -> tier height along the model's own column (see module docstring)
            cell_t, cell_td = temp_f, dew_f
            p_sfc = _val(h.get("surface_pressure"), i)
            z_cell = _height_at_pressure(levels, p_sfc) if (levels and p_sfc) else None
            shift_src = "column"
            if z_cell is not None:
                zl = [lv["z"] for lv in levels]
                tl_ = [lv["t"] for lv in levels]
                dl_ = [lv["td"] for lv in levels]
                d_t = _interp_at_height(zl, tl_, elevation_m) - _interp_at_height(zl, tl_, z_cell)
                d_td = _interp_at_height(zl, dl_, elevation_m) - _interp_at_height(zl, dl_, z_cell)
            elif p_sfc:
                z_cell = _std_height_m(p_sfc)
                d_t = d_td = -STD_LAPSE_C_PER_M * (elevation_m - z_cell)
                shift_src = "fixed 6.5 C/km (no column)"
            else:
                d_t = d_td = None
                shift_src = "none (no surface pressure)"
            if d_t is not None and temp_f is not None:
                temp_f = temp_f + d_t * 1.8
                if dew_f is not None:
                    dew_f = min(temp_f, dew_f + d_td * 1.8)
                rh = None   # recomputed below from the moved temperature and dew point
            if dew_f is not None and (rh is None or d_t is not None):
                rh = min(100.0, 100 * es_water(f_to_c(dew_f)) / es_water(f_to_c(temp_f)))
            if d_t is not None:   # Open-Meteo's wet bulb belongs to the cell; recompute at the tier
                wb_f = c_to_f(wet_bulb_psychro_c(f_to_c(temp_f), f_to_c(dew_f), p_hpa)) if dew_f is not None else None
            else:
                wb_f = _val(h.get("wet_bulb_temperature_2m"), i)
                if wb_f is None and dew_f is not None:
                    wb_f = c_to_f(wet_bulb_psychro_c(f_to_c(temp_f), f_to_c(dew_f), p_hpa))
            if wb_f is None:
                wb_f = temp_f
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
            for a_, b_ in zip(above, above[1:]):
                if a_["p"] < 300:
                    break
                rhi = (a_["rhi"] + b_["rhi"]) / 2
                w = (a_["w"] + b_["w"]) / 2
                dz = b_["z"] - a_["z"]
                if rhi >= 95 and (w > 0 or not has_w):
                    wt = (w if has_w else 1.0) * dz   # lift x thickness, or thickness only without vertical-velocity data
                    num += wt * habit_slr((a_["t"] + b_["t"]) / 2)
                    den += wt
            slr_cobb = num / den if den > 0 else slr_k

            # Wind and free-air temperature at tier height
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
            zt = [lv["z"] for lv in levels]
            # free air only where the tier is above the column's ground (50 m tolerance); below it the
            # pressure-level values are the model's surface temperature extrapolated downward
            fa_ok = levels and levels[0]["z"] <= elevation_m and (ground is None or elevation_m >= ground - 50.0)
            fa_t = _interp_at_height(zt, [lv["t"] for lv in levels], elevation_m) if fa_ok else None

            # Primary SLR: Cobb-style, no empirical adjustment (bounded to a physical range)
            slr = max(3.0, min(30.0, slr_cobb))
            # Experimental (NOT calibrated): wind fragmentation + near-freezing caps
            slr_exp = slr * wind_factor(ws)
            if wb_c > -1.0:
                slr_exp = min(slr_exp, 9.0)
            if wb_c > 0.0:
                slr_exp = min(slr_exp, 7.0)
            slr_exp = max(3.0, slr_exp)

            snow = precip * frac * slr
            cum += snow
            cum_model += model_snow
            cum_k += precip * frac * slr_k
            cum_10 += precip * frac * 10.0
            cum_exp += precip * frac * slr_exp

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

            vis = _val(h.get("visibility"), i)
            steps.append({
                "time": _iso(t),
                "precip_in": round(precip, 3),
                "snowfall_rate_in_hr": round(snow, 2),
                "cumulative_snow_inches": round(cum, 2),
                "model_snowfall_in_hr": round(model_snow, 2),
                "model_cumulative_inches": round(cum_model, 2),
                "kuchera_cumulative_inches": round(cum_k, 2),
                "experimental_cumulative_inches": round(cum_exp, 2),
                "slr": round(slr, 1),
                "slr_kuchera": round(slr_k, 1),
                "slr_experimental": round(slr_exp, 1),
                "snow_fraction": round(frac, 2),
                "precip_phase": phase,
                "precip_phase_label": {"dry": "None", "snow": "Snow", "mix": "Rain/snow", "rain": "Rain", "ice": "Sleet/freezing rain risk"}[phase],
                "precip_probability": pop,
                "pop_source": "ensemble" if ens_pop else "model",
                "chance_snow_pct": round(pop * frac),
                "chance_rain_pct": round(pop * (1 - frac)),
                "temp_f": round(temp_f, 1),
                "free_air_temp_f": round(c_to_f(fa_t), 1) if fa_t is not None else None,
                "cell_temp_f": round(cell_t, 1) if cell_t is not None else None,
                "cell_elevation_ft": round(z_cell * M_TO_FT) if z_cell is not None else None,
                "temp_shift_f": round(d_t * 1.8, 1) if d_t is not None else None,
                "fixed_lapse_shift_f": round(-STD_LAPSE_C_PER_M * (elevation_m - z_cell) * 1.8, 1) if z_cell is not None else None,
                "temp_shift_source": shift_src,
                "wet_bulb_f": round(wb_f, 1),
                "dew_point_f": round(dew_f, 1) if dew_f is not None else None,
                "dew_point_depression_f": round(temp_f - dew_f, 1) if dew_f is not None else None,
                "relative_humidity_pct": round(rh) if rh is not None else None,
                "mixing_ratio_g_kg": round(mixing_ratio_g_kg(f_to_c(dew_f), p_hpa), 2) if dew_f is not None else None,
                "visibility_mi": round(vis * vis_to_mi, 2) if vis is not None else None,
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

        return self._summarize_tier(steps, level_name, elev_ft, ensemble, has_w)

    def _summarize_tier(self, steps: List[Dict[str, Any]], level_name: str, elev_ft: int,
                        ensemble: Optional[Dict[str, Any]], has_w: bool, nbm: bool = False) -> Dict[str, Any]:
        def total(key, n_):
            return round(sum(s[key] for s in steps[:n_]), 1)

        def last(key, n_):
            return round(steps[min(n_, len(steps)) - 1][key], 1) if steps else 0.0

        def liquid_weighted(key, n_):
            wet = [s for s in steps[:n_] if s["precip_in"] >= 0.01 and (s.get("snow_fraction") or 0) > 0 and s.get(key) is not None]
            tot = sum(s["precip_in"] for s in wet)
            return round(sum(s[key] * s["precip_in"] for s in wet) / tot, 1) if tot > 0 else None

        daily = self._daily_rollup(steps)
        ens = self._ensemble_summary(ensemble, steps, daily) if ensemble else None
        adj = None
        first = [s for s in steps[:24] if s.get("cell_elevation_ft") is not None]
        if first:
            med = lambda vals: sorted(vals)[len(vals) // 2] if vals else None
            sh = [s["temp_shift_f"] for s in first if s.get("temp_shift_f") is not None]
            fx = [s["fixed_lapse_shift_f"] for s in first if s.get("fixed_lapse_shift_f") is not None]
            adj = {"method": "model grid cell moved to the tier height along the model's own column",
                   "cell_elevation_ft": med([s["cell_elevation_ft"] for s in first]), "target_elevation_ft": elev_ft,
                   "temp_shift_f": {"median": med(sh), "min": min(sh), "max": max(sh)} if sh else None,
                   "fixed_lapse_shift_f": med(fx),
                   "hours_without_column": sum(1 for s in steps if s.get("temp_shift_source") != "column")}
        if ens:
            by_date = {d["date"]: d for d in ens["daily"]}
            for d in daily:
                e = by_date.get(d["date"])
                if e:
                    d.update({"snow_p10": e["p10"], "snow_p25": e["p25"], "snow_p50": e["p50"], "snow_p75": e["p75"],
                              "snow_p90": e["p90"], "prob_6in": e["prob_6in"], "prob_12in": e["prob_12in"]})

        liq48 = sum(s["precip_in"] * (s.get("snow_fraction") or 0) for s in steps[:48])
        liq7 = sum(s["precip_in"] * (s.get("snow_fraction") or 0) for s in steps)
        return {
            "level": level_name,
            "elevation_ft": elev_ft,
            "hours_available": len(steps),
            "_steps": steps,
            "elevation_adjustment": adj,
            "ensemble": ens,
            "snow_24h_inches": total("snowfall_rate_in_hr", 24),
            "snow_48h_inches": total("snowfall_rate_in_hr", 48),
            "snow_72h_inches": total("snowfall_rate_in_hr", 72),
            "snow_7d_total_inches": total("snowfall_rate_in_hr", 168),
            "model_raw_snow_48h_inches": total("model_snowfall_in_hr", 48),
            "model_raw_snow_7d_inches": total("model_snowfall_in_hr", 168),
            "liquid_24h_inches": round(sum(s["precip_in"] for s in steps[:24]), 2),
            "liquid_48h_inches": round(sum(s["precip_in"] for s in steps[:48]), 2),
            "liquid_7d_inches": round(sum(s["precip_in"] for s in steps), 2),
            "slr_methods": ({
                "nbm": {"slr_48h": liquid_weighted("slr", 48), "slr_7d": liquid_weighted("slr", 168),
                        "snow_48h": total("snowfall_rate_in_hr", 48), "snow_7d": total("snowfall_rate_in_hr", 168)},
                "fixed_10": {"slr_48h": 10.0, "slr_7d": 10.0, "snow_48h": round(liq48 * 10, 1), "snow_7d": round(liq7 * 10, 1)},
            } if nbm else {
                "cobb": {"slr_48h": liquid_weighted("slr", 48), "slr_7d": liquid_weighted("slr", 168),
                         "snow_48h": total("snowfall_rate_in_hr", 48), "snow_7d": total("snowfall_rate_in_hr", 168),
                         "lift_weighted": has_w},
                "experimental_adjusted": {"slr_48h": liquid_weighted("slr_experimental", 48), "slr_7d": liquid_weighted("slr_experimental", 168),
                                          "snow_48h": last("experimental_cumulative_inches", 48), "snow_7d": last("experimental_cumulative_inches", 168)},
                "kuchera": {"slr_48h": liquid_weighted("slr_kuchera", 48), "slr_7d": liquid_weighted("slr_kuchera", 168),
                            "snow_48h": last("kuchera_cumulative_inches", 48), "snow_7d": last("kuchera_cumulative_inches", 168)},
                "fixed_10": {"slr_48h": 10.0, "slr_7d": 10.0, "snow_48h": round(liq48 * 10, 1), "snow_7d": round(liq7 * 10, 1)},
                "model_field_7to1": {"slr_48h": 7.0, "slr_7d": 7.0, "snow_48h": total("model_snowfall_in_hr", 48), "snow_7d": total("model_snowfall_in_hr", 168)},
            }),
            "daily_forecast": daily,
            "hourly_timeline_48h": steps[:TIMELINE_HOURS],
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
        factor = [s["snow_factor"] if s.get("snow_factor") is not None else (s.get("snow_fraction") or 0) * (s.get("slr") or 0) for s in steps]
        dates = [(datetime.fromisoformat(s["time"].replace("Z", "+00:00")) - timedelta(hours=8)).strftime("%Y-%m-%d") for s in steps]
        day_keys = [d["date"] for d in daily]
        ens_times = [t + "Z" if not t.endswith("Z") else t for t in h.get("time", [])]
        offset = 0
        if steps and ens_times:
            t0 = steps[0]["time"].replace(":00Z", "").rstrip("Z")
            offset = next((i for i, t in enumerate(ens_times) if t.startswith(t0[:13])), 0)
        members = []
        for k in keys:
            arr = h[k]
            if arr is None or sum(1 for x in arr[:len(steps)] if x is not None) < len(steps) * 0.5:
                continue
            snow = [((arr[i + offset] or 0.0) * factor[i]) if i + offset < len(arr) else 0.0 for i in range(len(steps))]
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
            "member_snow": {"h24": sorted(round(m["h24"], 1) for m in members), "h48": sorted(round(m["h48"], 1) for m in members),
                            "d7": sorted(round(m["d7"], 1) for m in members)},
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
