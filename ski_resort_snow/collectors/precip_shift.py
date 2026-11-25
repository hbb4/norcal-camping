"""Precipitation elevation shift from a model's own neighborhood (TUNING_PLAN.md 9b, item a).

A model's precipitation at a point is taken from the cells around it, not just the one cell the
point falls in: a distance-weighted line through the cells' amounts against their terrain height
(plus distance across the Sierra crest when there are 5 or more cells), evaluated at the point's
height and position. The same function scores the hindcast (neighborhood_hindcast.py) and corrects
the live forecast (open_meteo_client.py), so the two cannot drift apart.

The fit is linear in the amounts: for a fixed set of cells, the estimate is a weighted sum of the
cells' values, with weights that depend only on the geometry. line_weights() returns those weights
once, and they apply to every hour (or day) of the series. The weights sum to 1, so where all the
cells agree (for example HRRR/GFS after 48 h, when the GFS cells are coarser than the HRRR
neighborhood) the estimate equals that value. Low cells can get negative weights when the point is
above them; a negative estimate is clipped to zero on the running total (shift_hourly).

A residual multiplier per model (fitted against the SQV and WC3 pillows after the shift) is applied
on top; see neighborhood_hindcast.py fit.
"""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from .nbm_downscale import wls, _xy, _cross
except ImportError:  # run as a script from collectors/
    from nbm_downscale import wls, _xy, _cross

M_TO_FT = 3.28084
LAKE_TAHOE_FT = 6225     # cells over the lake come back from Open-Meteo at 0 ft; the model surface there is the lake
LAKE_MAX_FT = 3000       # any cell reported below this in the Tahoe area is a water cell
MAX_EXTRAP_FT = 1000     # the point's height is capped at 1,000 ft beyond the highest / lowest cell, as for NBM
MIN_RANGE_FT = 150       # cells must span at least this much height for a slope
MIN_CELLS = 3
CROSS_MIN_CELLS = 5      # the cross-crest term needs this many cells
MIN_DIST_KM = 0.5        # distance floor for the weights 1/d
# approximate grid step (degrees) of each Open-Meteo model, used to reach its neighboring cells
GRID_STEP_DEG = {"ecmwf_ifs": 0.09, "ecmwf_aifs025_single": 0.25, "gfs_seamless": 0.03, "ncep_rrfs_conus": 0.03,
                 "icon_seamless": 0.125, "ukmo_seamless": 0.12, "gem_seamless": 0.1}


def cell_height_ft(elev_m: Optional[float]) -> Tuple[Optional[float], bool]:
    """(height in ft, is a lake cell) from the elevation Open-Meteo reports for a cell."""
    if elev_m is None:
        return None, False
    ft = elev_m * M_TO_FT
    if ft < LAKE_MAX_FT:
        return float(LAKE_TAHOE_FT), True
    return ft, False


def dist_km(lat: float, lon: float, lat0: float, lon0: float) -> float:
    return math.hypot((lat - lat0) * 111.0, (lon - lon0) * 111.0 * math.cos(math.radians(lat0)))


def line_weights(cells: Sequence[Dict[str, Any]], lat: float, lon: float, z_ft: float) -> Tuple[Optional[List[float]], Dict[str, Any]]:
    """Weights a_i so that estimate = sum(a_i * value_i) is the line fit evaluated at the point.

    cells: [{"lat", "lon", "z" (ft or None)}]. Cells with no height get weight 0.
    Returns (weights, info) or (None, info) when the cells can't support a line (too few, too flat)."""
    use = [i for i, c in enumerate(cells) if c.get("z") is not None]
    info: Dict[str, Any] = {"cells": len(use)}
    if len(use) < MIN_CELLS:
        info["reason"] = f"fewer than {MIN_CELLS} cells with a height"
        return None, info
    zs = [cells[i]["z"] for i in use]
    zmin, zmax = min(zs), max(zs)
    info.update({"cell_min_ft": round(zmin), "cell_max_ft": round(zmax)})
    if zmax - zmin <= MIN_RANGE_FT:
        info["reason"] = f"cells span under {MIN_RANGE_FT} ft"
        return None, info
    z_eff = max(zmin - MAX_EXTRAP_FT, min(zmax + MAX_EXTRAP_FT, z_ft))
    info["evaluated_at_ft"] = round(z_eff)
    xc_site = _cross(*_xy(lat, lon))
    use_x = len(use) >= CROSS_MIN_CELLS
    info["cross_crest"] = use_x
    X = [[1.0, (cells[i]["z"] - z_ft) / 1000.0] + ([_cross(*_xy(cells[i]["lat"], cells[i]["lon"])) - xc_site] if use_x else []) for i in use]
    w = [1.0 / max(MIN_DIST_KM, dist_km(cells[i]["lat"], cells[i]["lon"], lat, lon)) for i in use]
    out = [0.0] * len(cells)
    # the estimate is linear in y: solve once per unit vector to get each cell's weight
    for k, i in enumerate(use):
        y = [1.0 if kk == k else 0.0 for kk in range(len(use))]
        cf = wls(X, y, w)
        if not cf:
            info["reason"] = "singular fit"
            return None, info
        out[i] = cf[0] + cf[1] * (z_eff - z_ft) / 1000.0
    return out, info


def estimate(values: Sequence[Optional[float]], weights: Sequence[float]) -> Optional[float]:
    """Line estimate (clipped at 0) from one value per cell; None when a weighted cell has no value."""
    tot = 0.0
    for v, a in zip(values, weights):
        if a == 0.0:
            continue
        if v is None:
            return None
        tot += a * v
    return max(0.0, tot)


def shift_hourly(series: Sequence[Sequence[Optional[float]]], weights: Sequence[float]) -> List[Optional[float]]:
    """Hourly amounts at the point from each cell's hourly amounts (series[i][t]).

    The weighted sum is taken on the running totals, clipped at zero and held from falling, so the
    hourly amounts are never negative and the total over any window matches the line fit of that
    window's totals except where the fit dips below an earlier high."""
    n = max((len(s) for s in series), default=0)
    out: List[Optional[float]] = []
    cum = [0.0] * len(series)
    held = 0.0
    for t in range(n):
        vals = {i: (s[t] if t < len(s) else None) for i, s in enumerate(series) if weights[i] != 0.0}
        if any(v is None for v in vals.values()):
            out.append(None)      # a weighted cell is missing this hour: no estimate, totals carry on
            continue
        for i, v in vals.items():
            cum[i] += v
        c = max(0.0, sum(a * cum[i] for i, a in enumerate(weights) if a != 0.0))
        inc = max(0.0, c - held)
        held = max(held, c)
        out.append(inc)
    return out
