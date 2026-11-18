"""California Data Exchange Center (CDEC) & USDA NRCS SNOTEL Telemetry Client.

Fetches automated ground sensor data for snow depth, snow water equivalent (SWE),
snow density (SLR), and temperature from mountain weather stations:
- Station SQV: Squaw Valley Gold Coast (Elevation 8,010')
- Station WC3: Ward Creek #3 / Alpine Meadows border (Elevation 6,750')
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional


class CDECSnotelClient:
    """Client for querying California Data Exchange Center (CDEC) automated snow sensors."""

    CDEC_JSON_URL = "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet"

    def __init__(self, timeout_sec: int = 10):
        self.timeout_sec = timeout_sec

    def fetch_station_telemetry(
        self,
        station_id: str,
        elevation_ft: int,
        station_name: str
    ) -> Dict[str, Any]:
        """Fetch hourly sensor records for SWE (sensor 3), snow depth (sensor 82), and temp (sensor 6)."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=2)
        start_date_str = yesterday.strftime("%Y-%m-%d")

        params = {
            "Stations": station_id,
            "SensorNums": "3,82,6",
            "dur_code": "H",
            "Start": start_date_str
        }
        url = f"{self.CDEC_JSON_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SkiResortSnowDashboard/1.0 (outdoor-planning)"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                records = json.loads(response.read().decode("utf-8"))
                return self._parse_telemetry(records, station_id, elevation_ft, station_name)
        except Exception as e:
            return {
                "status": "error",
                "source": f"CDEC Automated Telemetry ({station_id})",
                "station_id": station_id,
                "elevation_ft": elevation_ft,
                "timestamp_utc": now.isoformat(),
                "error_message": str(e),
                "fallback_available": True
            }

    def _parse_telemetry(
        self,
        records: List[Dict[str, Any]],
        station_id: str,
        elevation_ft: int,
        station_name: str
    ) -> Dict[str, Any]:
        """Process hourly records and extract current depth, 24h delta, SWE, and snow density."""
        swe_readings = []
        depth_readings = []
        temp_readings = []

        for rec in records:
            sensor = rec.get("sensorNum")
            val = rec.get("value")
            dt = rec.get("date")

            if val is None or float(val) < -90:  # CDEC missing values are often -9999
                continue

            float_val = float(val)
            entry = {"date": dt, "value": float_val}

            if sensor == 3:  # SWE (inches)
                swe_readings.append(entry)
            elif sensor == 82:  # Snow depth (inches)
                depth_readings.append(entry)
            elif sensor == 6:  # Temperature (Fahrenheit)
                temp_readings.append(entry)

        current_depth = depth_readings[-1]["value"] if depth_readings else 0.0
        depth_24h_ago = depth_readings[-25]["value"] if len(depth_readings) >= 25 else (depth_readings[0]["value"] if depth_readings else current_depth)
        snow_depth_24h_delta = max(0.0, round(current_depth - depth_24h_ago, 1))

        current_swe = swe_readings[-1]["value"] if swe_readings else 0.0
        swe_24h_ago = swe_readings[-25]["value"] if len(swe_readings) >= 25 else (swe_readings[0]["value"] if swe_readings else current_swe)
        swe_24h_delta = max(0.0, round(current_swe - swe_24h_ago, 2))

        current_temp = temp_readings[-1]["value"] if temp_readings else None

        # Compute Snow-to-Liquid Ratio (SLR)
        if swe_24h_delta > 0.1 and snow_depth_24h_delta > 0:
            slr = round(snow_depth_24h_delta / swe_24h_delta, 1)
        else:
            slr = 12.0  # Default Sierra average

        # Characterize snow quality based on SLR
        if slr >= 16.0:
            snow_character = "Cold Blower Powder (Dry / Fluffy)"
        elif slr >= 11.0:
            snow_character = "Classic Tahoe Powder (Packed / Responsive)"
        elif slr >= 7.0:
            snow_character = "Dense Sierra Cement (High Moisture)"
        else:
            snow_character = "Very Wet / Rain-Affected Slush"

        return {
            "status": "success",
            "source": f"CDEC Ground Telemetry ({station_id})",
            "station_id": station_id,
            "station_name": station_name,
            "elevation_ft": elevation_ft,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "measurements": {
                "snow_depth_current_inches": round(current_depth, 1),
                "snow_depth_24h_gain_inches": snow_depth_24h_delta,
                "swe_current_inches": round(current_swe, 2),
                "swe_24h_gain_inches": swe_24h_delta,
                "snow_to_liquid_ratio": slr,
                "snow_density_classification": snow_character,
                "air_temperature_f": round(current_temp, 1) if current_temp is not None else None
            }
        }
