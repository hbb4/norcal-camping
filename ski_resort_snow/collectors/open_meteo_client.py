"""Open-Meteo Client for High-Resolution Multi-Elevation Ski Snow Forecasts.

What this collector does (no API key needed):

1. Surface query at three elevations (base / mid / summit). Open-Meteo's
   `elevation=` parameter downscales temperature, dew point and the model's
   own rain/snow split to that height, so each tier gets its own surface
   weather.
2. One upper-air query on pressure levels (850 to 400 hPa): temperature,
   relative humidity, geopotential height, vertical velocity and wind. That
   gives us a real model sounding for every forecast hour.

From the sounding we derive, per hour:

* Wet-bulb zero height (WBZ): where the wet-bulb temperature crosses 0 C.
  It tracks where falling snow melts better than the dry 0 C freezing level,
  because evaporation cools the air. Snow level is taken as roughly WBZ
  minus 500 ft, and each tier gets a snow fraction from where it sits
  relative to WBZ.
* Kuchera snow-to-liquid ratio (SLR) from the warmest temperature in the
  column between the tier and 500 hPa. Open-Meteo's own `snowfall` field uses
  a fixed ~7:1 ratio, which under-calls cold Sierra snow and over-calls wet
  snow. We keep the model value for comparison and show the SLR-adjusted
  amount as the primary number.
* Dendritic growth zone (DGZ, -12 to -18 C): its base and top height,
  thickness, mean RH and mean upward motion. Saturated air rising through a
  thick DGZ (the "crosshair" signature) is the best single predictor of
  efficient, high-ratio snowfall.
* Wind per tier: the 10 m model wind is a smoothed-terrain value and does
  not change with the `elevation=` parameter, so it understates exposed
  ridgetop wind. Summit uses free-air wind interpolated from pressure levels
  to the summit height, base uses the 10 m model wind (sheltered valley),
  and mid blends 60% of the way toward free-air.
* Surface mixing ratio (g/kg) at each tier: how much water vapour the low
  levels hold, i.e. how much liquid a storm can wring out.
"""

import json
import math
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

M_TO_FT = 3.28084
PRESSURE_LEVELS = [850, 800, 750, 700, 650, 600, 550, 500, 450, 400]
LEVEL_VARS = ["temperature", "relative_humidity", "geopotential_height",
              "vertical_velocity", "wind_speed", "wind_direction"]
TIMELINE_HOURS = 48
FORECAST_HOURS = 168


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


def std_pressure_hpa(height_m: float) -> float:
    return 1013.25 * (1.0 - 2.25577e-5 * height_m) ** 5.25588


def mixing_ratio_g_kg(dew_c: float, p_hpa: float) -> float:
    e = 6.112 * math.exp(17.67 * dew_c / (dew_c + 243.5))
    return 621.97 * e / max(1.0, p_hpa - e)


def kuchera_slr(t_max_k: float) -> float:
    """Kuchera snow ratio from the warmest temperature (K) in the column."""
    if t_max_k > 271.16:
        slr = 12.0 + 2.0 * (271.16 - t_max_k)
    else:
        slr = 12.0 + (271.16 - t_max_k)
    return max(4.0, min(25.0, slr))


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


def _val(arr, i, default=None):
    if arr is None or i >= len(arr) or arr[i] is None:
        return default
    return float(arr[i])


class OpenMeteoClient:
    """Client for Open-Meteo mountain weather with sounding-derived snow diagnostics."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    USER_AGENT = "SierraSnowDashboard/3.0"

    def __init__(self, timeout_sec: int = 15):
        self.timeout_sec = timeout_sec

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def fetch_resort_forecast(
        self,
        lat: float,
        lon: float,
        base_elevation_m: int,
        summit_elevation_m: int,
        mid_elevation_m: Optional[int] = None,
        timezone_str: str = "America/Los_Angeles"
    ) -> Dict[str, Any]:
        if mid_elevation_m is None:
            mid_elevation_m = int((base_elevation_m + summit_elevation_m) / 2)
        tiers = {"base": base_elevation_m, "mid": mid_elevation_m, "summit": summit_elevation_m}
        labels = {"base": "Base Area", "mid": "Mid Mountain", "summit": "Summit Ridge"}

        try:
            surface = {k: self._query_surface(lat, lon, m) for k, m in tiers.items()}
            upper = self._query_upper_air(lat, lon)
            profile = self._build_vertical_profile(upper, surface["base"], base_elevation_m)

            exposure = {"base": 0.0, "mid": 0.6, "summit": 1.0}
            parsed = {k: self._build_tier(surface[k], profile, labels[k], tiers[k], exposure[k]) for k in tiers}
            sounding = self._summarize_sounding(profile, parsed, tiers)

            summit = parsed["summit"]
            gusts48 = [s["gust_mph"] for s in summit["hourly_timeline_48h"]]
            fl48 = [p["freezing_level_ft"] for p in profile[:TIMELINE_HOURS] if p["freezing_level_ft"]]

            return {
                "status": "success",
                "source": "Open-Meteo best-match models (HRRR / GFS / ECMWF blend) + pressure-level sounding",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "base": {k: v for k, v in parsed["base"].items() if k != "hourly_timeline_48h"},
                "mid": {k: v for k, v in parsed["mid"].items() if k != "hourly_timeline_48h"},
                "summit": {k: v for k, v in parsed["summit"].items() if k != "hourly_timeline_48h"},
                "base_48h_inches": parsed["base"]["snow_48h_inches"],
                "mid_48h_inches": parsed["mid"]["snow_48h_inches"],
                "summit_48h_inches": summit["snow_48h_inches"],
                "summit_7d_total_inches": summit["snow_7d_total_inches"],
                "peak_gust_summit_mph": round(max(gusts48 or [0.0]), 1),
                "avg_freezing_level_ft": round(sum(fl48) / len(fl48)) if fl48 else None,
                "elevation_timelines": {k: parsed[k]["hourly_timeline_48h"] for k in tiers},
                "hourly_timeline": summit["hourly_timeline_48h"],
                "vertical_profile": profile[:TIMELINE_HOURS],
                "atmospheric_sounding": sounding,
                "methodology": {
                    "snowfall": "precip x snow fraction (from wet-bulb zero height) x Kuchera SLR",
                    "model_snowfall": "Open-Meteo raw snowfall (fixed ~7:1 ratio) kept for comparison",
                    "wind": "free-air wind interpolated from pressure levels to tier height; gusts scaled by model 10 m gust factor"
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "source": "Open-Meteo",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_message": f"{type(e).__name__}: {e}",
                "fallback_available": True
            }

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _get(self, params: Dict[str, str]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))

    def _query_surface(self, lat: float, lon: float, elevation_m: int) -> Dict[str, Any]:
        return self._get({
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "elevation": str(elevation_m),
            "hourly": ",".join([
                "snowfall", "rain", "precipitation", "precipitation_probability",
                "temperature_2m", "dew_point_2m", "relative_humidity_2m",
                "wet_bulb_temperature_2m", "freezing_level_height",
                "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "weather_code"
            ]),
            "forecast_hours": str(FORECAST_HOURS),
            "past_hours": "0",
            "timezone": "GMT",
            "precipitation_unit": "inch",
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
        })

    def _query_upper_air(self, lat: float, lon: float) -> Dict[str, Any]:
        hourly = [f"{v}_{p}hPa" for p in PRESSURE_LEVELS for v in LEVEL_VARS]
        return self._get({
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": ",".join(hourly),
            "forecast_hours": str(FORECAST_HOURS),
            "past_hours": "0",
            "timezone": "GMT",
            "wind_speed_unit": "mph",
        })

    # ------------------------------------------------------------------
    # Sounding
    # ------------------------------------------------------------------
    def _build_vertical_profile(self, upper: Dict[str, Any], base_sfc: Dict[str, Any], base_elev_m: int) -> List[Dict[str, Any]]:
        """Per-hour column diagnostics: WBZ, freezing level, DGZ, lift."""
        uh = upper.get("hourly", {})
        bh = base_sfc.get("hourly", {})
        times = uh.get("time", [])
        out = []
        for i, t in enumerate(times):
            levels = []
            for p in PRESSURE_LEVELS:
                z = _val(uh.get(f"geopotential_height_{p}hPa"), i)
                tc = _val(uh.get(f"temperature_{p}hPa"), i)
                rh = _val(uh.get(f"relative_humidity_{p}hPa"), i)
                if z is None or tc is None or rh is None:
                    continue
                levels.append({
                    "p": p, "z": z, "t": tc, "rh": rh,
                    "tw": wet_bulb_stull_c(tc, rh),
                    # Open-Meteo reports vertical velocity with negative = rising
                    # (pressure-coordinate sign). Flip so positive = ascent.
                    "w": -_val(uh.get(f"vertical_velocity_{p}hPa"), i, 0.0),
                    "ws": _val(uh.get(f"wind_speed_{p}hPa"), i),
                    "wd": _val(uh.get(f"wind_direction_{p}hPa"), i),
                })
            # Free-air column only (850 hPa sits below the base and gives the
            # upwind low-level temperature). Tier surface values are used per tier.
            base_tw_f = _val(bh.get("wet_bulb_temperature_2m"), i)
            base_tw = f_to_c(base_tw_f) if base_tw_f is not None else None
            levels.sort(key=lambda lv: lv["z"])
            zs = [lv["z"] for lv in levels]

            wbz_m = _interp_height_for_value(zs, [lv["tw"] for lv in levels], 0.0)
            fzl_m = _interp_height_for_value(zs, [lv["t"] for lv in levels], 0.0)
            # NB: with precipitation_unit=inch Open-Meteo returns this in FEET
            model_fzl_ft = _val(bh.get("freezing_level_height"), i)

            dgz_bot = _interp_height_for_value(zs, [lv["t"] for lv in levels], -12.0)
            dgz_top = _interp_height_for_value(zs, [lv["t"] for lv in levels], -18.0)
            dgz_rh = dgz_w = None
            if dgz_bot is not None and dgz_top is not None and dgz_top > dgz_bot:
                samples = [h for h in (dgz_bot, (dgz_bot + dgz_top) / 2, dgz_top)]
                dgz_rh = sum(_interp_at_height(zs, [lv["rh"] for lv in levels], h) for h in samples) / 3
                dgz_w = sum(_interp_at_height(zs, [lv["w"] for lv in levels], h) for h in samples) / 3

            def ft(m):
                return round(m * M_TO_FT) if m is not None else None

            wbz_ft = ft(wbz_m)
            column_cold = bool(levels) and levels[0]["tw"] <= 0
            if wbz_ft is None and column_cold:
                # Entire column below 0 C wet-bulb, even at 850 hPa
                wbz_ft_effective = ft(levels[0]["z"])
            else:
                wbz_ft_effective = wbz_ft

            out.append({
                "time": t + "Z" if not t.endswith("Z") else t,
                "freezing_level_ft": ft(fzl_m) if fzl_m is not None else (round(model_fzl_ft) if model_fzl_ft is not None else None),
                "wet_bulb_zero_ft": wbz_ft_effective,
                "wbz_below_850hpa": wbz_ft is None and column_cold,
                "base_wet_bulb_c": round(base_tw, 1) if base_tw is not None else None,
                "snow_level_ft": (wbz_ft_effective - 500) if wbz_ft_effective is not None else None,
                "dgz_base_ft": ft(dgz_bot),
                "dgz_top_ft": ft(dgz_top),
                "dgz_thickness_ft": ft(dgz_top - dgz_bot) if (dgz_bot is not None and dgz_top is not None) else None,
                "dgz_rh_pct": round(dgz_rh) if dgz_rh is not None else None,
                "dgz_lift_cm_s": round(dgz_w * 100, 1) if dgz_w is not None else None,
                "_levels": levels,  # stripped before output
            })
        return out

    # ------------------------------------------------------------------
    # Per-tier timeline
    # ------------------------------------------------------------------
    def _build_tier(self, data: Dict[str, Any], profile: List[Dict[str, Any]], level_name: str, elevation_m: int, exposure: float = 1.0) -> Dict[str, Any]:
        """exposure: 0 = sheltered valley (use model 10 m wind), 1 = exposed ridge (free-air wind)."""
        h = data.get("hourly", {})
        times = h.get("time", [])
        elev_ft = round(elevation_m * M_TO_FT)
        p_hpa = std_pressure_hpa(elevation_m)

        steps = []
        cum = cum_model = 0.0
        for i, t in enumerate(times):
            prof = profile[i] if i < len(profile) else {}
            levels = prof.get("_levels", [])

            precip = _val(h.get("precipitation"), i, 0.0)
            model_snow = _val(h.get("snowfall"), i, 0.0)
            pop = int(_val(h.get("precipitation_probability"), i, 0.0))
            temp_f = _val(h.get("temperature_2m"), i, 30.0)
            dew_f = _val(h.get("dew_point_2m"), i, temp_f - 4)
            rh = _val(h.get("relative_humidity_2m"), i, 85.0)
            wb_f = _val(h.get("wet_bulb_temperature_2m"), i)
            if wb_f is None:
                wb_f = c_to_f(wet_bulb_stull_c(f_to_c(temp_f), rh))

            # Snow fraction from position relative to the wet-bulb zero height.
            # Fully snow at/above WBZ, fully rain 1,000 ft below it.
            wbz = prof.get("wet_bulb_zero_ft")
            if wbz is None:
                frac = 1.0 if wb_f <= 33.0 else 0.0
            else:
                frac = max(0.0, min(1.0, (elev_ft - (wbz - 1000)) / 1000.0))
            # Surface cross-check: a clearly sub-freezing wet bulb is snow
            # regardless; a warm one (> 36 F) can't be accumulating snow.
            if wb_f <= 31.0:
                frac = 1.0
            elif wb_f >= 36.0:
                frac = 0.0

            # Kuchera SLR: warmest temp between this tier and 500 hPa
            col = [f_to_c(temp_f)] + [lv["t"] for lv in levels if lv["z"] >= elevation_m and (lv["p"] is None or lv["p"] >= 500)]
            slr = kuchera_slr(max(col) + 273.15)

            snow = precip * frac * slr
            cum += snow
            cum_model += model_snow

            wet = precip >= 0.005
            if not wet and pop < 20:
                phase = "dry"
            elif frac >= 0.9:
                phase = "snow"
            elif frac <= 0.1:
                phase = "rain"
            else:
                phase = "mix"

            # Free-air wind at tier height from pressure levels
            lv_wind = [lv for lv in levels if lv["ws"] is not None]
            zs = [lv["z"] for lv in lv_wind]
            ws10 = _val(h.get("wind_speed_10m"), i, 0.0)
            g10 = _val(h.get("wind_gusts_10m"), i, ws10 * 1.4)
            if lv_wind:
                ws = _interp_at_height(zs, [lv["ws"] for lv in lv_wind], elevation_m)
                u = _interp_at_height(zs, [-lv["ws"] * math.sin(math.radians(lv["wd"])) for lv in lv_wind], elevation_m)
                v = _interp_at_height(zs, [-lv["ws"] * math.cos(math.radians(lv["wd"])) for lv in lv_wind], elevation_m)
                wd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
                free_air = ws
                ws = ws10 + exposure * max(0.0, free_air - ws10)
            else:
                free_air, ws, wd = ws10, ws10, _val(h.get("wind_direction_10m"), i, 0.0)
            gust_factor = max(1.15, min(1.4, g10 / ws10)) if ws10 > 3 else 1.3
            gust = max(g10, ws * gust_factor)

            steps.append({
                "time": t + "Z" if not t.endswith("Z") else t,
                "precip_in": round(precip, 3),
                "snowfall_rate_in_hr": round(snow, 2),
                "cumulative_snow_inches": round(cum, 2),
                "model_snowfall_in_hr": round(model_snow, 2),
                "model_cumulative_inches": round(cum_model, 2),
                "slr": round(slr, 1),
                "snow_fraction": round(frac, 2),
                "precip_phase": phase,
                "precip_phase_label": {"dry": "Dry", "snow": "Snow", "mix": "Rain/snow mix", "rain": "Rain"}[phase],
                "precip_probability": pop,
                "chance_snow_pct": round(pop * frac),
                "chance_rain_pct": round(pop * (1 - frac)),
                "temp_f": round(temp_f, 1),
                "wet_bulb_f": round(wb_f, 1),
                "dew_point_f": round(dew_f, 1),
                "relative_humidity_pct": round(rh),
                "mixing_ratio_g_kg": round(mixing_ratio_g_kg(f_to_c(dew_f), p_hpa), 2),
                "wind_mph": round(ws, 1),
                "gust_mph": round(gust, 1),
                "wind_dir_deg": round(wd),
                "model_10m_wind_mph": round(ws10, 1),
                "free_air_wind_mph": round(free_air, 1),
                "freezing_level_ft": prof.get("freezing_level_ft"),
                "snow_level_ft": prof.get("snow_level_ft"),
                "wet_bulb_zero_ft": prof.get("wet_bulb_zero_ft"),
            })

        def total(n):
            return round(sum(s["snowfall_rate_in_hr"] for s in steps[:n]), 1)

        def model_total(n):
            return round(sum(s["model_snowfall_in_hr"] for s in steps[:n]), 1)

        return {
            "level": level_name,
            "elevation_ft": elev_ft,
            "snow_24h_inches": total(24),
            "snow_48h_inches": total(48),
            "snow_72h_inches": total(72),
            "snow_7d_total_inches": total(168),
            "model_raw_snow_48h_inches": model_total(48),
            "model_raw_snow_7d_inches": model_total(168),
            "liquid_48h_inches": round(sum(s["precip_in"] for s in steps[:48]), 2),
            "daily_forecast": self._daily_rollup(steps),
            "hourly_timeline_48h": steps[:TIMELINE_HOURS],
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
            out.append({
                "date": d,
                "snowfall_inches": round(sum(x["snowfall_rate_in_hr"] for x in ss), 1),
                "temp_high_f": max(x["temp_f"] for x in ss),
                "temp_low_f": min(x["temp_f"] for x in ss),
                "max_gust_mph": max(x["gust_mph"] for x in ss),
            })
        return out

    # ------------------------------------------------------------------
    # Summary cards
    # ------------------------------------------------------------------
    def _summarize_sounding(self, profile: List[Dict[str, Any]], parsed: Dict[str, Any], tiers: Dict[str, int]) -> Dict[str, Any]:
        window = profile[:24]
        summit_tl = parsed["summit"]["hourly_timeline_48h"][:24]
        base_tl = parsed["base"]["hourly_timeline_48h"][:24]
        # Focus the summary on hours where it's actually precipitating, if any
        wet_idx = [i for i, s in enumerate(summit_tl) if s["precip_in"] >= 0.01] or list(range(len(window)))
        wp = [window[i] for i in wet_idx if i < len(window)]

        def avg(vals):
            vals = [v for v in vals if v is not None]
            return sum(vals) / len(vals) if vals else None

        dgz_b, dgz_t = avg([p["dgz_base_ft"] for p in wp]), avg([p["dgz_top_ft"] for p in wp])
        dgz_rh = avg([p["dgz_rh_pct"] for p in wp])
        dgz_lift = avg([p["dgz_lift_cm_s"] for p in wp])
        thick = (dgz_t - dgz_b) if (dgz_b and dgz_t) else 0
        crosshair_hours = sum(1 for p in window if (p["dgz_rh_pct"] or 0) >= 85 and (p["dgz_lift_cm_s"] or 0) >= 10)
        slr_avg = avg([s["slr"] for i, s in enumerate(summit_tl) if i in wet_idx])

        if dgz_rh is not None and dgz_rh >= 85 and (dgz_lift or 0) >= 10:
            status, regime = "ACTIVE_BLOWER", "Dendrites: saturated, rising DGZ (crosshair)"
            desc = (f"The -12 to -18 C layer is saturated ({dgz_rh:.0f}% RH) and rising at "
                    f"{dgz_lift:.0f} cm/s during precip hours. That's the setup for big, fluffy dendrites "
                    f"and high snow ratios. {crosshair_hours} of the next 24 h show this signature.")
        elif dgz_rh is not None and dgz_rh >= 70:
            status, regime = "MODERATE", "Mixed plates, columns and some dendrites"
            desc = (f"DGZ is moist ({dgz_rh:.0f}% RH) but lift through it is weak "
                    f"({(dgz_lift or 0):.0f} cm/s). Expect ordinary snow ratios.")
        else:
            status, regime = "WEAK_DRY", "Rimed crystals / graupel likely"
            desc = (f"DGZ is dry ({(dgz_rh or 0):.0f}% RH). Snow that does fall will mostly grow "
                    f"by riming lower down: denser, smaller flakes.")

        fl = avg([p["freezing_level_ft"] for p in wp])
        wbz = avg([p["wet_bulb_zero_ft"] for p in wp])
        snow_lvl = avg([p["snow_level_ft"] for p in wp])
        base_ft = round(tiers["base"] * M_TO_FT)
        summit_ft = round(tiers["summit"] * M_TO_FT)
        if snow_lvl is None or base_ft > snow_lvl + 500:
            risk = f"LOW: base ({base_ft:,}') sits above the snow level (~{(snow_lvl or 0):,.0f}'). All snow."
        elif base_ft >= snow_lvl:
            risk = f"MODERATE: base ({base_ft:,}') is close to the snow level (~{snow_lvl:,.0f}'). Wet snow or mix possible."
        else:
            risk = f"HIGH: snow level (~{snow_lvl:,.0f}') is above the base ({base_ft:,}'). Rain at the base."

        def phase_text(tl):
            wet = [s for s in tl if s["precip_in"] >= 0.01]
            if not wet:
                return "Dry"
            f = sum(s["snow_fraction"] * s["precip_in"] for s in wet) / sum(s["precip_in"] for s in wet)
            return f"{round(f * 100)}% snow"

        base_mr = avg([s["mixing_ratio_g_kg"] for s in base_tl])
        if base_mr is None:
            base_mr = 0
        # Thresholds for ~800 hPa (6,000-7,000 ft), where air holds less vapour than at sea level
        if base_mr >= 5.0:
            moist = "Warm, moisture-rich (atmospheric-river type): heavy water content, dense snow"
        elif base_mr >= 2.5:
            moist = "Typical cold Pacific storm moisture"
        else:
            moist = "Very cold, dry air: light, low-water snow"

        summit_winds = [s["wind_mph"] for s in summit_tl]
        dirs = [s["wind_dir_deg"] for s in summit_tl]
        mean_dir = round(math.degrees(math.atan2(sum(math.sin(math.radians(d)) for d in dirs),
                                                 sum(math.cos(math.radians(d)) for d in dirs))) % 360) if dirs else 0
        compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][round(mean_dir / 22.5) % 16]
        # Sierra crest runs NNW-SSE; flow from WSW-SW hits it head-on.
        oro = "STRONG (flow perpendicular to crest)" if 200 <= mean_dir <= 290 else ("PARTIAL" if 160 <= mean_dir <= 320 else "WEAK / downslope")

        for p in profile:
            p.pop("_levels", None)

        return {
            "dgz": {
                "base_elevation_ft": round(dgz_b) if dgz_b else None,
                "top_elevation_ft": round(dgz_t) if dgz_t else None,
                "thickness_ft": round(thick),
                "relative_humidity_pct": round(dgz_rh) if dgz_rh is not None else None,
                "lift_cm_s": round(dgz_lift, 1) if dgz_lift is not None else None,
                "crosshair_hours_24h": crosshair_hours,
                "status": status,
                "crystal_regime": regime,
                "description": desc,
                "avg_summit_slr": round(slr_avg, 1) if slr_avg else None,
            },
            "precipitation_phase_analysis": {
                "current_freezing_level_ft": round(fl) if fl else None,
                "wet_bulb_zero_ft": round(wbz) if wbz else None,
                "effective_snow_level_ft": round(snow_lvl) if snow_lvl else None,
                "base_village_elevation_ft": base_ft,
                "summit_elevation_ft": summit_ft,
                "valley_mix_risk": risk,
                "base_wet_bulb_f": round(avg([s["wet_bulb_f"] for s in base_tl]) or 0, 1),
                "phase_breakdown": {
                    "summit": phase_text(summit_tl),
                    "mid": phase_text(parsed["mid"]["hourly_timeline_48h"][:24]),
                    "base": phase_text(base_tl),
                },
            },
            "moisture_and_dynamics": {
                "surface_mixing_ratio_g_kg": round(base_mr, 1),
                "moisture_category": moist,
                "crest_700hpa_jet_mph": round(avg(summit_winds) or 0),
                "peak_crest_gust_mph": round(max([s["gust_mph"] for s in summit_tl] or [0]), 1),
                "crest_700hpa_wind_dir": f"{mean_dir}° ({compass})",
                "orographic_lift_index": oro,
            },
        }
