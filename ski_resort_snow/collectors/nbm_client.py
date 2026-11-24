"""NOAA National Blend of Models (NBM v4, CONUS 2.5 km) from NOMADS, NBM-only.

Fields (all NBM's own, nearest 2.5 km grid point to each query point):
  TMP, DPT, RH (2 m) · WIND, GUST, WDIR (10 m) · VIS · TCDC
  APCP  precipitation (1 h to 48 h, then 6 h)
  ASNOW snowfall (NBM's own amount, same windows)
  SNOWLR NBM snow/liquid ratio · SNOWLVL NBM snow level (m MSL)
  APCP probability > 0.254 mm  -> chance of precipitation

Files: https://nomads.ncep.noaa.gov/cgi-bin/filter_blend.pl subset to a small box
around the resorts (simple-packed GRIB2, decoded by grib2_simple.py).
Cycles 00/06/12/18Z reach 264 h; hours 1-48 are hourly, then 6-hourly here
(3-hourly files exist but only carry 6 h accumulations).
One cycle is fetched once and cached in data/cache/.
"""

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from . import http_ssl  # noqa: F401
    from .grib2_simple import read_messages, nearest_index, _lambert_latlon
except ImportError:
    import http_ssl  # noqa: F401
    from grib2_simple import read_messages, nearest_index, _lambert_latlon

BASE = "https://nomads.ncep.noaa.gov"
FILTER = BASE + "/cgi-bin/filter_blend.pl"
BOX = {"toplat": 39.26, "bottomlat": 39.10, "leftlon": -120.36, "rightlon": -120.14}
VARS = ["TMP", "DPT", "RH", "WIND", "GUST", "WDIR", "VIS", "TCDC", "APCP", "ASNOW", "SNOWLR", "SNOWLVL"]
LEVELS = ["2_m_above_ground", "10_m_above_ground", "surface", "0_m_above_mean_sea_level"]
HOURS = list(range(1, 49)) + list(range(54, 169, 6))
USER_AGENT = "SierraSnowDashboard/3.0"
CACHE_VERSION = 2   # 2: also stores every grid point in BOX (for elevation adjustment)
M_TO_FT = 3.28084


def _k_to_f(k):
    return None if k is None else (k - 273.15) * 9 / 5 + 32


class NBMClient:
    def __init__(self, cache_dir: Path, timeout_sec: int = 30, pause_s: float = 0.4):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_sec = timeout_sec
        self.pause_s = pause_s

    # ------------------------------------------------------------------ cycle
    def _exists(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status == 200
        except Exception:
            return False

    def latest_cycle(self) -> Optional[datetime]:
        now = datetime.now(timezone.utc)
        t = now.replace(minute=0, second=0, microsecond=0, hour=(now.hour // 6) * 6)
        for _ in range(6):
            d, h = t.strftime("%Y%m%d"), t.strftime("%H")
            if self._exists(f"{BASE}/pub/data/nccf/com/blend/prod/blend.{d}/{h}/core/blend.t{h}z.core.f168.co.grib2.idx"):
                return t
            t -= timedelta(hours=6)
        return None

    # ------------------------------------------------------------------ fetch
    def fetch(self, points: Dict[str, Dict[str, float]], progress=None) -> Dict[str, Any]:
        """points: {key: {"lat", "lon"}} -> {cycle, points: {key: {grid_lat, grid_lon, rows}}}."""
        say = progress or (lambda m: None)
        cyc = self.latest_cycle()
        if not cyc:
            return {"status": "error", "error_message": "no complete NBM cycle found on NOMADS"}
        key = cyc.strftime("%Y%m%d%H")
        cache = self.cache_dir / f"nbm_{key}.json"
        if cache.exists():
            data = json.loads(cache.read_text())
            if set(points) <= set(data.get("points", {})) and data.get("cache_version") == CACHE_VERSION:
                data["from_cache"] = True
                return data
        d, h = cyc.strftime("%Y%m%d"), cyc.strftime("%H")
        out = {k: {"rows": {}} for k in points}
        box: Dict[str, Any] = {"latlon": None, "rows": {}}
        grid_cache: Dict = {}
        idx_cache: Dict = {}
        def get(fh):
            params = [("dir", f"/blend.{d}/{h}/core"), ("file", f"blend.t{h}z.core.f{fh:03d}.co.grib2")]
            params += [(f"var_{v}", "on") for v in VARS] + [(f"lev_{lv}", "on") for lv in LEVELS]
            params += [("subregion", "")] + [(k, str(v)) for k, v in BOX.items()]
            url = FILTER + "?" + urllib.parse.urlencode(params)
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=self.timeout_sec) as r:
                        buf = r.read()
                    if buf.startswith(b"GRIB"):
                        return fh, buf
                except Exception:
                    pass
                time.sleep(2 + attempt * 3)
            return fh, None

        from concurrent.futures import ThreadPoolExecutor
        failures = 0
        done = 0
        with ThreadPoolExecutor(max_workers=4) as pool:   # modest concurrency for NOMADS
            for fh, buf in pool.map(get, HOURS):
                done += 1
                if done % 12 == 0:
                    say(f"NBM {h}Z: {done}/{len(HOURS)} files")
                if not buf:
                    failures += 1
                    continue
                for m in read_messages(buf):
                    f = self._field(m)
                    if not f:
                        continue
                    gk = tuple(sorted((a, b) for a, b in m["grid"].items() if a != "tmpl"))
                    for k, p in points.items():
                        if (k, gk) not in idx_cache:
                            idx_cache[(k, gk)] = nearest_index(m["grid"], p["lat"], p["lon"], grid_cache)
                        i, glat, glon = idx_cache[(k, gk)]
                        out[k]["grid_lat"], out[k]["grid_lon"] = round(glat, 4), round(glon, 4)
                        out[k]["rows"].setdefault(str(fh), {})[f] = m["values"][i]
                    # the filtered file holds only the BOX subgrid, so keep all of it
                    if box["latlon"] is None:
                        box["latlon"] = [[round(a, 4), round(b, 4)] for a, b in _lambert_latlon(m["grid"])]
                        box["nx"], box["ny"] = m["grid"]["nx"], m["grid"]["ny"]
                    if len(m["values"]) == len(box["latlon"]):
                        box["rows"].setdefault(str(fh), {})[f] = [None if v is None else round(v, 3) for v in m["values"]]
        if failures > len(HOURS) // 4:
            return {"status": "error", "error_message": f"NBM download incomplete ({failures} of {len(HOURS)} files failed)"}
        data = {"status": "success", "cache_version": CACHE_VERSION, "cycle_utc": cyc.isoformat(), "points": out, "box": box, "failures": failures,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat()}
        cache.write_text(json.dumps(data))
        for old in sorted(self.cache_dir.glob("nbm_*.json"))[:-4]:
            old.unlink()
        return data

    @staticmethod
    def _field(m: Dict[str, Any]) -> Optional[str]:
        c, p, pdt, lt, lv = (m["cat"], m["par"]), m["pdt"], m["pdt"], m["lev_type"], m["lev_val"]
        cp = (m["cat"], m["par"])
        if m["disc"] != 0:
            return None
        if pdt == 0:
            if cp == (0, 0) and lt == 103 and lv == 2: return "tmp_k"
            if cp == (0, 6) and lt == 103 and lv == 2: return "dpt_k"
            if cp == (1, 1) and lt == 103 and lv == 2: return "rh"
            if cp == (2, 1) and lt == 103 and lv == 10: return "wind_ms"
            if cp == (2, 22) and lt == 103 and lv == 10: return "gust_ms"
            if cp == (2, 0) and lt == 103 and lv == 10: return "wdir"
            if cp == (19, 0) and lt == 1: return "vis_m"
            if cp == (6, 1) and lt == 1: return "tcdc"
            if cp == (1, 233) and lt == 1: return "slr"
            if cp == (19, 236) and lt == 102: return "snowlvl_m"
        if pdt == 8:
            if cp == (1, 8): return f"apcp_{m['acc_len']}h"
            if cp == (1, 29): return f"asnow_{m['acc_len']}h"
        if pdt == 9 and cp == (1, 8) and m.get("prob_type") == 1:
            return f"pop_{m['acc_len']}h"
        return None

    # ------------------------------------------------------------------ to timeline
    @staticmethod
    def to_steps(cycle_iso: str, rows: Dict[str, Dict[str, float]], elevation_ft: float, start: datetime) -> List[Dict[str, Any]]:
        """Hourly steps from `start` (current hour) to 168 h. Hours past 48 come from
        6 h NBM values: accumulations spread evenly over the 6 hours, other fields
        linearly interpolated (flagged interpolated=True)."""
        cyc = datetime.fromisoformat(cycle_iso)
        known = {int(k): v for k, v in rows.items()}
        hrs = sorted(known)
        inst = ["tmp_k", "dpt_k", "rh", "wind_ms", "gust_ms", "vis_m", "tcdc", "slr", "snowlvl_m"]

        def interp(fh, key):
            if fh in known and known[fh].get(key) is not None:
                return known[fh][key]
            lo = max([h for h in hrs if h <= fh and known[h].get(key) is not None], default=None)
            hi = min([h for h in hrs if h >= fh and known[h].get(key) is not None], default=None)
            if lo is None or hi is None:
                return None
            if lo == hi:
                return known[lo][key]
            return known[lo][key] + (known[hi][key] - known[lo][key]) * (fh - lo) / (hi - lo)

        def wdir(fh):
            lo = max([h for h in hrs if h <= fh and known[h].get("wdir") is not None], default=None)
            return known[lo]["wdir"] if lo is not None else None

        steps = []
        first = max(1, int((start - cyc).total_seconds() // 3600))
        cum = 0.0
        for fh in range(first, first + 168):
            if fh > max(hrs or [0]):
                break
            if fh <= 48:
                r = known.get(fh, {})
                apcp_mm, asnow_m, pop = r.get("apcp_1h"), r.get("asnow_1h"), r.get("pop_1h")
            else:
                end = int(math.ceil(fh / 6) * 6)
                r = known.get(end, {})
                apcp_mm = (r.get("apcp_6h") / 6) if r.get("apcp_6h") is not None else None
                asnow_m = (r.get("asnow_6h") / 6) if r.get("asnow_6h") is not None else None
                pop = r.get("pop_6h")
            liq = (apcp_mm or 0.0) / 25.4
            snow = (asnow_m or 0.0) * 39.3701
            slr = interp(fh, "slr")
            tf, df = _k_to_f(interp(fh, "tmp_k")), _k_to_f(interp(fh, "dpt_k"))
            sl_m = interp(fh, "snowlvl_m")
            sl_ft = sl_m * M_TO_FT if sl_m is not None else None
            frac = None
            if liq >= 0.004 and slr:
                frac = max(0.0, min(1.0, snow / (liq * slr)))
            elif sl_ft is not None:
                frac = 1.0 if elevation_ft >= sl_ft else 0.0
            if liq < 0.004 and (pop or 0) < 20:
                phase = "dry"
            elif frac is None or frac >= 0.9:
                phase = "snow"
            elif frac <= 0.1:
                phase = "rain"
            else:
                phase = "mix"
            cum += snow
            vis = interp(fh, "vis_m")
            ws, gs = interp(fh, "wind_ms"), interp(fh, "gust_ms")
            steps.append({
                "time": (cyc + timedelta(hours=fh)).strftime("%Y-%m-%dT%H:%MZ"),
                "lead_h": fh, "interpolated": fh > 48,
                "precip_in": round(liq, 3), "snowfall_rate_in_hr": round(snow, 2), "cumulative_snow_inches": round(cum, 2),
                "model_snowfall_in_hr": round(snow, 2), "model_cumulative_inches": round(cum, 2),
                "slr": round(slr, 1) if slr is not None else None, "snow_fraction": round(frac, 2) if frac is not None else None,
                "snow_factor": round(snow / liq, 2) if liq >= 0.004 else ((slr or 0) * (frac if frac is not None else 0)),
                "precip_phase": phase,
                "precip_phase_label": {"dry": "None", "snow": "Snow", "mix": "Rain/snow", "rain": "Rain"}[phase],
                "precip_probability": round(pop) if pop is not None else None, "pop_source": "NBM",
                "temp_f": round(tf, 1) if tf is not None else None,
                "dew_point_f": round(df, 1) if df is not None else None,
                "dew_point_depression_f": round(tf - df, 1) if (tf is not None and df is not None) else None,
                "relative_humidity_pct": round(interp(fh, "rh")) if interp(fh, "rh") is not None else None,
                "visibility_mi": round(vis / 1609.344, 2) if vis is not None else None,
                "cloud_cover_pct": round(interp(fh, "tcdc")) if interp(fh, "tcdc") is not None else None,
                "wind_mph": round(ws * 2.23694, 1) if ws is not None else None,
                "gust_mph": round(gs * 2.23694, 1) if gs is not None else None,
                "wind_dir_deg": round(wdir(fh)) if wdir(fh) is not None else None,
                "snow_level_ft": round(sl_ft) if sl_ft is not None else None,
                "freezing_level_ft": None, "free_air_temp_f": None, "wet_bulb_zero_ft": None,
            })
        return steps
