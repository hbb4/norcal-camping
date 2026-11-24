"""Terrain height of 2.5 km NBM grid points.

NBM's CONUS grid and the NWS forecast grid (NDFD) share the same 2.5 km cells:
the NWS gridpoint whose cell contains an NBM grid point is centered on it
(checked at Palisades: 39.2073,-120.2862 -> STO 88,88 centered 39.2076,-120.2864).
NBM files carry no terrain field, so the cell elevation reported by
api.weather.gov (/gridpoints/{wfo}/{x},{y} -> properties.elevation) is used.
Terrain is static, so results are cached permanently in config/grid_terrain.json.
"""

import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from . import http_ssl  # noqa: F401
except ImportError:
    import http_ssl  # noqa: F401

USER_AGENT = "SierraSnowDashboard/3.0 (terrain lookup)"
M_TO_FT = 3.28084


def _get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def terrain_ft(latlons: List[Tuple[float, float]], cache_path: Path, pause_s: float = 0.25,
               progress=None) -> Dict[str, Optional[dict]]:
    """{"lat,lon": {"elevation_ft", "wfo", "x", "y"}} for each point (cached)."""
    cache_path = Path(cache_path)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [(a, b) for a, b in latlons if _key(a, b) not in cache]
    for n, (lat, lon) in enumerate(todo):
        try:
            p = _get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")["properties"]
            g = _get(f"https://api.weather.gov/gridpoints/{p['gridId']}/{p['gridX']},{p['gridY']}")
            elev_m = (g.get("properties", {}).get("elevation") or {}).get("value")
            cache[_key(lat, lon)] = {"elevation_ft": round(elev_m * M_TO_FT) if elev_m is not None else None,
                                     "wfo": p["gridId"], "x": p["gridX"], "y": p["gridY"]}
        except Exception as e:  # leave it out; a later run retries
            if progress:
                progress(f"terrain lookup failed at {lat:.4f},{lon:.4f}: {e}")
        if progress and (n + 1) % 10 == 0:
            progress(f"grid terrain {n + 1}/{len(todo)}")
        time.sleep(pause_s)
    if todo:
        cache_path.write_text(json.dumps(cache, indent=0, sort_keys=True))
    return {_key(a, b): cache.get(_key(a, b)) for a, b in latlons}
