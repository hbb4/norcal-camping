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
        """Fetch hourly SWE (sensor 3), snow depth (18, or 82 at some sites) and air temp (4)."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=2)
        start_date_str = yesterday.strftime("%Y-%m-%d")

        params = {
            "Stations": station_id,
            "SensorNums": "3,4,18,82",
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

        for rec in sorted(records, key=lambda r: str(r.get("date", ""))):
            sensor = rec.get("SENSOR_NUM", rec.get("sensorNum"))
            val = rec.get("value")
            dt = rec.get("date")

            if val is None or float(val) < -90:  # CDEC missing values are often -9999
                continue

            entry = {"date": dt, "value": float(val)}
            if sensor == 3:          # SWE (inches)
                swe_readings.append(entry)
            elif sensor in (18, 82):  # Snow depth (inches)
                depth_readings.append(entry)
            elif sensor == 4:        # Air temperature (F)
                temp_readings.append(entry)

        if not depth_readings and not swe_readings:
            return {
                "status": "no_data",
                "source": f"CDEC Ground Telemetry ({station_id})",
                "station_id": station_id, "station_name": station_name, "elevation_ft": elevation_ft,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_message": "No snow sensor readings returned",
            }

        def latest(r):
            return r[-1]["value"] if r else None

        def gain(r, hours):
            if len(r) < 2:
                return None
            ago = r[-(hours + 1)]["value"] if len(r) > hours else r[0]["value"]
            return max(0.0, round(r[-1]["value"] - ago, 2))

        current_depth = latest(depth_readings)
        current_swe = latest(swe_readings)
        current_temp = latest(temp_readings)
        snow_depth_24h_delta = gain(depth_readings, 24)
        swe_24h_delta = gain(swe_readings, 24)
        depth_48h = gain(depth_readings, 48)
        swe_48h = gain(swe_readings, 48)

        # Measured snow-to-liquid ratio from the storm's depth vs. SWE gain
        slr = None
        for dd, sw in ((snow_depth_24h_delta, swe_24h_delta), (depth_48h, swe_48h)):
            if dd and sw and sw >= 0.3 and dd >= 2:
                slr = round(dd / sw, 1)
                break

        # Characterize snow quality based on SLR
        if slr is None:
            snow_character = "Not enough new snow to measure"
        elif slr >= 16.0:
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
                "snow_depth_current_inches": round(current_depth, 1) if current_depth is not None else None,
                "snow_depth_24h_gain_inches": snow_depth_24h_delta,
                "snow_depth_48h_gain_inches": depth_48h,
                "swe_current_inches": round(current_swe, 2) if current_swe is not None else None,
                "swe_24h_gain_inches": swe_24h_delta,
                "swe_48h_gain_inches": swe_48h,
                "snow_to_liquid_ratio": slr,
                "snow_density_classification": snow_character,
                "air_temperature_f": round(current_temp, 1) if current_temp is not None else None
            }
        }

    def fetch_window(self, station_id: str, start_utc: datetime, end_utc: datetime) -> Optional[Dict[str, Any]]:
        """SWE and depth change at a station between two UTC times.

        CDEC hourly data is in Pacific Standard Time (UTC-8). Endpoint values
        use the median of the readings within 2 h of each end to damp pillow noise."""
        pst = timedelta(hours=-8)
        s_loc, e_loc = start_utc + pst, end_utc + pst
        params = {"Stations": station_id, "SensorNums": "3,18,82", "dur_code": "H",
                  "Start": (s_loc - timedelta(days=1)).strftime("%Y-%m-%d"), "End": (e_loc + timedelta(days=1)).strftime("%Y-%m-%d")}
        url = f"{self.CDEC_JSON_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SkiResortSnowDashboard/1.0 (outdoor-planning)"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                records = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        series = {"swe": [], "depth": []}
        for rec in records:
            v = rec.get("value")
            if v is None or float(v) < -90:
                continue
            try:
                t = datetime.strptime(rec["date"], "%Y-%m-%d %H:%M")
            except (KeyError, ValueError):
                continue
            sensor = rec.get("SENSOR_NUM", rec.get("sensorNum"))
            key = "swe" if sensor == 3 else ("depth" if sensor in (18, 82) else None)
            if key:
                series[key].append((t, float(v)))

        def at(rows, t_loc):
            near = sorted(v for (t, v) in rows if abs((t - t_loc.replace(tzinfo=None)).total_seconds()) <= 7200)
            return near[len(near) // 2] if near else None

        def gain(rows):
            a, b = at(rows, s_loc), at(rows, e_loc)
            return round(b - a, 2) if a is not None and b is not None else None

        return {"swe_gain_in": gain(series["swe"]), "depth_gain_in": gain(series["depth"]),
                "swe_start_in": at(series["swe"], s_loc), "swe_end_in": at(series["swe"], e_loc)}
