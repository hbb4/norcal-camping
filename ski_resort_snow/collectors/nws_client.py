"""NOAA / National Weather Service (NWS) Client.

Fetches official NWS Reno (REV) forecasts, Quantitative Snowfall Grids,
and active Winter Weather Hazards / Advisories without requiring an API key.
"""

import json
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional


class NWSClient:
    """Client for querying the US National Weather Service API."""

    USER_AGENT = "SkiResortSnowDashboard/1.0 (github.com/camping/ski_resort_snow)"

    def __init__(self, timeout_sec: int = 10):
        self.timeout_sec = timeout_sec

    def fetch_resort_forecast(
        self,
        lat: float,
        lon: float,
        wfo: str = "REV",
        grid_x: int = 41,
        grid_y: int = 82,
        summit_lat: Optional[float] = None,
        summit_lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Alerts, text periods and the Area Forecast Discussion from the office covering
        (lat, lon); gridded snowfall at (lat, lon) and, if given, at the summit point,
        which can fall in a different office's grid (the Sierra crest is the REV/STO boundary)."""
        try:
            # Resolve the real forecast grid cell for these coordinates
            # (configured grid values can be stale or wrong).
            try:
                wfo, grid_x, grid_y = self._resolve_grid(lat, lon)
            except Exception:
                pass
            alerts = self._fetch_active_alerts(lat, lon)
            periods, synoptic = self._fetch_forecast_periods(wfo, grid_x, grid_y)
            grid_snow = self._fetch_grid_snowfall(wfo, grid_x, grid_y)
            parsed_totals = self._parse_snow_from_periods(periods)
            discussion = self._fetch_discussion(wfo)

            summit_grid = None
            if summit_lat is not None:
                try:
                    s_wfo, s_x, s_y = self._resolve_grid(summit_lat, summit_lon)
                    sg = self._fetch_grid_snowfall(s_wfo, s_x, s_y)
                    summit_grid = {"wfo": s_wfo, "x": s_x, "y": s_y, "lat": summit_lat, "lon": summit_lon, **sg}
                except Exception:
                    summit_grid = None
            primary = summit_grid if summit_grid and summit_grid.get("next_24h_inches") is not None else grid_snow
            # Area Forecast Discussions: the resort's office first, then the summit-cell office if different
            discussions = [{"office": wfo, "role": "resort office (base point)", "text": discussion}]
            if summit_grid and summit_grid.get("wfo") and summit_grid["wfo"] != wfo:
                discussions.append({"office": summit_grid["wfo"], "role": "summit grid office (west slope)",
                                    "text": self._fetch_discussion(summit_grid["wfo"])})
            snow_24 = primary.get("next_24h_inches")
            snow_48 = primary.get("next_48h_inches")
            if snow_24 is None and periods:
                snow_24 = parsed_totals.get("snow_24h_expected")
                snow_48 = parsed_totals.get("snow_48h_expected")

            return {
                "status": "success",
                "source": f"NWS {wfo}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "grid": {"wfo": wfo, "x": grid_x, "y": grid_y, "elevation_ft": grid_snow.get("grid_elevation_ft"),
                         "lat": lat, "lon": lon, "next_24h_inches": grid_snow.get("next_24h_inches"),
                         "next_48h_inches": grid_snow.get("next_48h_inches"), "total_snow_inches": grid_snow.get("total_snow_inches"),
                         "total_through_utc": grid_snow.get("total_through_utc")},
                "summit_grid": summit_grid,
                "snowfall_grid_used": "summit" if primary is summit_grid else "base",
                "office": wfo,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "active_hazards": alerts,
                "synoptic_headline": synoptic,
                "synoptic_discussion": discussion or synoptic,
                "discussions": discussions,
                "forecast_periods": periods[:6],
                "forecast_24h_expected_inches": snow_24,
                "forecast_48h_expected_inches": snow_48,
                "snowfall_forecast": {
                    "snow_24h_min_inches": parsed_totals.get("snow_24h_min", 0.0),
                    "snow_24h_max_inches": parsed_totals.get("snow_24h_max", 0.0),
                    "text_24h_expected_inches": parsed_totals.get("snow_24h_expected", 0.0),
                    "text_48h_expected_inches": parsed_totals.get("snow_48h_expected", 0.0),
                    "grid_next_24h_inches": snow_24,
                    "grid_next_48h_inches": snow_48,
                    "grid_7d_inches": primary.get("total_snow_inches"),
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "source": f"NOAA / NWS Reno ({wfo})",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e),
                "fallback_available": True
            }

    def fetch_cells_snowfall(self, cells: Dict[str, Dict[str, Any]], cache_path, max_age_s: int = 7200, progress=None) -> Dict[str, Any]:
        """Gridded snowfall (next 24 h, 48 h, grid total) at several NWS cells, keyed "WFO/x/y".
        Used to move the NWS forecast to each tier's elevation with the same local regression
        as NBM. Cached for max_age_s because each /gridpoints response is large."""
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        cache_path = Path(cache_path)
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text())
            except Exception:
                cache = {}
        now = datetime.now(timezone.utc)
        fresh = lambda e: e and (now - datetime.fromisoformat(e["fetched_at_utc"])).total_seconds() < max_age_s
        todo = [k for k in cells if not fresh(cache.get(k))]

        def one(k):
            wfo, x, y = k.split("/")
            r = self._fetch_grid_snowfall(wfo, int(x), int(y))
            return k, ({**r, "fetched_at_utc": now.isoformat()} if r else None)
        if todo:
            with ThreadPoolExecutor(max_workers=4) as pool:
                for n, (k, r) in enumerate(pool.map(one, todo)):
                    if r:
                        cache[k] = r
                    if progress and (n + 1) % 10 == 0:
                        progress(f"NWS grid cells {n + 1}/{len(todo)}")
            cache_path.write_text(json.dumps(cache))
        return {k: cache.get(k) for k in cells}

    def _get_json(self, url: str) -> Dict[str, Any]:
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "application/geo+json"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))

    def _resolve_grid(self, lat: float, lon: float) -> tuple:
        p = self._get_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")["properties"]
        return p["gridId"], int(p["gridX"]), int(p["gridY"])

    def _fetch_discussion(self, wfo: str) -> Optional[str]:
        """Latest Area Forecast Discussion: the .KEY MESSAGES / .SYNOPSIS section, trimmed."""
        try:
            listing = self._get_json(f"https://api.weather.gov/products/types/AFD/locations/{wfo}")
            latest = listing.get("@graph", [])[0]
            text = self._get_json(f"https://api.weather.gov/products/{latest['id']}").get("productText", "")
        except Exception:
            return None
        sections = re.split(r"\n(?=\.[A-Z][A-Z /]+\.\.\.)", text)
        pick = next((sec for key in (".KEY MESSAGES", ".SYNOPSIS", ".SHORT TERM", ".DISCUSSION")
                     for sec in sections if sec.strip().startswith(key)), None)
        if not pick:
            return None
        body = re.sub(r"^\.[A-Z][A-Z /]+\.\.\.\s*", "", pick.strip())
        body = re.split(r"\n\s*&&", body)[0]
        # unwrap the 66-column teletype lines but keep paragraph breaks
        paras = [" ".join(line.strip() for line in para.splitlines()) for para in re.split(r"\n\s*\n", body)]
        out = "\n\n".join(p for p in paras if p)
        issued = latest.get("issuanceTime", "")
        return (out[:1800] + ("…" if len(out) > 1800 else "")) + (f"\n\nIssued {issued[:16].replace('T', ' ')} UTC" if issued else "")

    def _fetch_active_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Fetch active winter weather warnings, watches, and advisories for coordinates."""
        url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "application/geo+json"})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                data = json.loads(response.read().decode("utf-8"))
                features = data.get("features", [])
                alerts = []
                for f in features:
                    props = f.get("properties", {})
                    event = props.get("event", "Weather Alert")
                    severity = props.get("severity", "Unknown")
                    headline = props.get("headline", "")
                    description = props.get("description", "")
                    instruction = props.get("instruction", "")
                    alerts.append({
                        "event": event,
                        "severity": severity,
                        "headline": headline,
                        "description": description[:500] + ("..." if len(description) > 500 else ""),
                        "instruction": instruction[:300] + ("..." if len(instruction) > 300 else "")
                    })
                return alerts
        except Exception:
            return []

    def _fetch_forecast_periods(self, wfo: str, grid_x: int, grid_y: int) -> tuple:
        """Fetch 12-hour period text forecasts."""
        url = f"https://api.weather.gov/gridpoints/{wfo}/{grid_x},{grid_y}/forecast"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "application/geo+json"})

        with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
            data = json.loads(response.read().decode("utf-8"))
            props = data.get("properties", {})
            periods = props.get("periods", [])
            synoptic = periods[0].get("shortForecast", "Fair") if periods else "Fair"
            return periods, synoptic

    def _fetch_grid_snowfall(self, wfo: str, grid_x: int, grid_y: int) -> Dict[str, Any]:
        """Official gridded snowfall (mm per interval) summed over the next 24h / 48h / all."""
        try:
            props = self._get_json(f"https://api.weather.gov/gridpoints/{wfo}/{grid_x},{grid_y}").get("properties", {})
        except Exception:
            return {}
        now = datetime.now(timezone.utc)
        tot = {24: 0.0, 48: 0.0, None: 0.0}
        last_end = None
        values = props.get("snowfallAmount", {}).get("values", [])
        for item in values:
            val = item.get("value")
            vt = item.get("validTime", "")
            if val is None or "/" not in vt:
                continue
            start_s, dur_s = vt.split("/")
            start = datetime.fromisoformat(start_s)
            m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?", dur_s)
            hours = (int(m.group(1) or 0) * 24 + int(m.group(2) or 0)) if m else 1
            end = start + timedelta(hours=max(1, hours))
            last_end = end if last_end is None or end > last_end else last_end
            for win in (24, 48, None):
                w_end = now + timedelta(hours=win) if win else end
                overlap = (min(end, w_end) - max(start, now)).total_seconds() / 3600
                if overlap > 0:
                    tot[win] += float(val) * min(1.0, overlap / max(1, hours))
        if not values:
            return {}
        elev = (props.get("elevation") or {}).get("value")
        return {"grid_elevation_ft": round(elev * 3.28084) if elev is not None else None,
                "next_24h_inches": round(tot[24] / 25.4, 1), "next_48h_inches": round(tot[48] / 25.4, 1),
                "total_snow_inches": round(tot[None] / 25.4, 1), "grid_points_count": len(values),
                "total_through_utc": last_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if last_end else None}

    def _parse_snow_from_periods(self, periods: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract numerical snowfall expectations from text forecasts like '3 to 6 inches'."""
        totals = {"24h_min": 0.0, "24h_max": 0.0, "48h_min": 0.0, "48h_max": 0.0}

        # Pattern: "accumulation of 3 to 7 inches" or "1 to 2 inches" or "around 4 inches"
        pattern_range = re.compile(r"(\d+)\s+to\s+(\d+)\s+inches", re.IGNORECASE)
        pattern_single = re.compile(r"(?:around|about|near|additional)?\s*(\d+)\s+inch(?:es)?", re.IGNORECASE)

        for idx, period in enumerate(periods[:4]):
            text = period.get("detailedForecast", "")
            match_range = pattern_range.search(text)
            match_single = pattern_single.search(text)

            low, high = 0.0, 0.0
            if match_range:
                low = float(match_range.group(1))
                high = float(match_range.group(2))
            elif match_single:
                val = float(match_single.group(1))
                low = val * 0.8
                high = val * 1.2

            if idx < 2:  # First 24 hours
                totals["24h_min"] += low
                totals["24h_max"] += high
            if idx < 4:  # First 48 hours
                totals["48h_min"] += low
                totals["48h_max"] += high

        exp_24h = round((totals["24h_min"] + totals["24h_max"]) / 2, 1)
        exp_48h = round((totals["48h_min"] + totals["48h_max"]) / 2, 1)

        return {
            "snow_24h_min": round(totals["24h_min"], 1),
            "snow_24h_max": round(totals["24h_max"], 1),
            "snow_24h_expected": exp_24h,
            "snow_48h_expected": exp_48h,
            "snow_72h_expected": round(exp_48h * 1.3, 1)
        }
