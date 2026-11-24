"""Observed radiosonde (weather balloon) soundings from the Iowa Environmental Mesonet.

Stations used for the Tahoe Sierra:
  KREV  Reno, NV (WMO 72489), 1,516 m, ~50 km east (downwind) of the crest
  KOAK  Oakland, CA (WMO 72493), 3 m, ~250 km west-southwest (upwind)

Launches are at 00Z and 12Z. Endpoint:
  https://mesonet.agron.iastate.edu/json/raob.py?station=KREV&ts=YYYYMMDDHHMM
"""

import json
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

STATIONS = {
    "KREV": {"name": "Reno, NV", "wmo": "72489", "elevation_m": 1516, "lat": 39.57, "lon": -119.80,
             "position": "~50 km east of the crest (downwind of the Sierra)"},
    "KOAK": {"name": "Oakland, CA", "wmo": "72493", "elevation_m": 3, "lat": 37.75, "lon": -122.22,
             "position": "~250 km west-southwest (upwind, Pacific inflow)"},
}


class RaobClient:
    URL = "https://mesonet.agron.iastate.edu/json/raob.py?station={station}&ts={ts}"
    USER_AGENT = "SierraSnowDashboard/3.0"

    def __init__(self, timeout_sec: int = 20):
        self.timeout_sec = timeout_sec

    def latest(self, station: str, max_lookback: int = 4) -> Dict[str, Any]:
        """Most recent available 00Z/12Z sounding (tries up to `max_lookback` launches back)."""
        now = datetime.now(timezone.utc) - timedelta(hours=1, minutes=30)  # data lands ~1.5 h after launch
        t = now.replace(minute=0, second=0, microsecond=0, hour=12 if now.hour >= 12 else 0)
        meta = STATIONS.get(station, {})
        last_err = None
        for _ in range(max_lookback):
            try:
                prof = self._fetch(station, t)
                if prof:
                    return {"status": "success", "station": station, **meta, "valid_utc": t.isoformat(),
                            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                            "source": f"IEM RAOB archive ({station})", "levels": prof}
            except Exception as e:  # network / parse
                last_err = str(e)
            t -= timedelta(hours=12)
        return {"status": "error", "station": station, **meta, "error_message": last_err or "no sounding in lookback window"}

    def _fetch(self, station: str, t: datetime) -> Optional[List[List[Any]]]:
        url = self.URL.format(station=station, ts=t.strftime("%Y%m%d%H%M"))
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as r:
            d = json.loads(r.read().decode("utf-8"))
        profiles = d.get("profiles") or []
        if not profiles:
            return None
        levels = []
        for lv in profiles[0].get("profile", []):
            p, z, t_c = lv.get("pres"), lv.get("hght"), lv.get("tmpc")
            if p is None or z is None or t_c is None or p < 100:
                continue
            td = lv.get("dwpc")
            wd, wk = lv.get("drct"), lv.get("sknt")
            # [p hPa, z m, T C, Td C, wind dir deg, wind speed mph, vertical velocity (n/a)]
            levels.append([round(p, 1), round(z), round(t_c, 1), round(td, 1) if td is not None else None,
                           round(wd) if wd is not None else None, round(wk * 1.15078) if wk is not None else None, None])
        levels.sort(key=lambda x: -x[0])
        return levels if len(levels) >= 10 else None
