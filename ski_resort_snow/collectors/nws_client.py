"""NOAA / National Weather Service (NWS) Client.

Fetches official NWS Reno (REV) forecasts, Quantitative Snowfall Grids,
and active Winter Weather Hazards / Advisories without requiring an API key.
"""

import json
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone
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
        grid_y: int = 82
    ) -> Dict[str, Any]:
        """Fetch NWS text forecast, snowfall amounts, and active winter weather alerts."""
        try:
            alerts = self._fetch_active_alerts(lat, lon)
            periods, synoptic = self._fetch_forecast_periods(wfo, grid_x, grid_y)
            grid_snow = self._fetch_grid_snowfall(wfo, grid_x, grid_y)

            # Calculate snow totals from periods and grid
            parsed_totals = self._parse_snow_from_periods(periods)

            return {
                "status": "success",
                "source": f"NOAA / NWS Reno ({wfo})",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "active_hazards": alerts,
                "synoptic_headline": synoptic,
                "forecast_periods": periods[:6],  # Next 3 days (day & night pairs)
                "snowfall_forecast": {
                    "snow_24h_min_inches": parsed_totals.get("snow_24h_min", 0.0),
                    "snow_24h_max_inches": parsed_totals.get("snow_24h_max", 0.0),
                    "snow_24h_expected_inches": parsed_totals.get("snow_24h_expected", 0.0),
                    "snow_48h_expected_inches": parsed_totals.get("snow_48h_expected", 0.0),
                    "snow_72h_expected_inches": parsed_totals.get("snow_72h_expected", 0.0),
                    "grid_total_snow_inches": grid_snow.get("total_snow_inches", 0.0)
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
        """Fetch quantitative snowfall amounts from NWS grid dataset."""
        url = f"https://api.weather.gov/gridpoints/{wfo}/{grid_x},{grid_y}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "application/geo+json"})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                data = json.loads(response.read().decode("utf-8"))
                props = data.get("properties", {})
                snowfall_grid = props.get("snowfallAmount", {}).get("values", [])

                total_mm = 0.0
                for item in snowfall_grid:
                    val = item.get("value")
                    if val is not None:
                        total_mm += float(val)

                total_inches = round(total_mm / 25.4, 1)
                return {"total_snow_inches": total_inches, "grid_points_count": len(snowfall_grid)}
        except Exception:
            return {"total_snow_inches": 0.0, "grid_points_count": 0}

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
