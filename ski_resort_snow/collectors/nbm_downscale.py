"""Elevation adjustment of NBM grid-point values to a target elevation.

The NBM is a 2.5 km grid, so a mountain tier rarely sits at its grid cell's terrain
height (Palisades mid 8,010 ft and summit 9,050 ft share one cell at 7,726 ft).
Instead of assuming a lapse rate or a snowfall-elevation rule, this module measures
NBM's own relationship with terrain around the target, separately at every forecast
hour, and moves the nearest grid point's value along it:

  value(target) = value(nearest cell) + b * (z_target - z_cell) [+ c * (x_target - x_cell)]

b (and c) come from a distance-weighted least-squares fit over the NBM cells within
RADIUS_KM of the target (Gaussian weights, SIGMA_KM). x is distance across the Sierra
crest (positive toward ENE), included for precipitation and snowfall because the
west slope gets more precipitation than the east side at the same height.

  temperature, dew point   elevation only; lapse clamped to [-5.5, +8] F per 1,000 ft
                           (dry adiabatic to a strong inversion)
  snow/liquid ratio        elevation only
  precipitation, snowfall  elevation + cross-crest, fit on the cumulative totals at each
                           hour (smoother than hourly amounts), kept non-decreasing
  wind, gusts, cloud, visibility, chance of precipitation, snow level   not adjusted

Leave-one-out check on the 2026-11-24 06Z cycle (each cell predicted from its
neighbors): 7-day snowfall MAE 1.64 in (nearest cell) -> 0.45 in (adjusted);
temperature ~1.8 F -> ~1.0 F; dew point 1.4 F -> 0.5 F. That checks consistency with
NBM's own field, not accuracy against observations (see TUNING_PLAN.md).
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

RADIUS_KM = 7.0
SIGMA_KM = 3.0
MAX_EXTRAP_FT = 1000.0          # beyond the highest/lowest neighbor, dz is capped
CREST_NORMAL_DEG = 70.0         # Sierra crest runs ~340/160 deg; normal toward ENE
LAPSE_BOUNDS_F_PER_KFT = (-5.5, 8.0)
KM_PER_DEG = 111.0


def _xy(lat: float, lon: float, lat0: float = 39.17, lon0: float = -120.25) -> Tuple[float, float]:
    return ((lon - lon0) * KM_PER_DEG * math.cos(math.radians(lat0)), (lat - lat0) * KM_PER_DEG)


def _cross(x: float, y: float) -> float:
    a = math.radians(CREST_NORMAL_DEG)
    return x * math.sin(a) + y * math.cos(a)


def wls(X: List[List[float]], y: List[float], w: List[float]) -> Optional[List[float]]:
    """Weighted least squares via normal equations (k <= 3)."""
    k = len(X[0])
    A = [[0.0] * (k + 1) for _ in range(k)]
    for xi, yi, wi in zip(X, y, w):
        for a in range(k):
            A[a][k] += wi * xi[a] * yi
            for c in range(k):
                A[a][c] += wi * xi[a] * xi[c]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        if abs(A[c][c]) < 1e-9:
            return None
        for r in range(k):
            if r != c:
                f = A[r][c] / A[c][c]
                for cc in range(c, k + 1):
                    A[r][cc] -= f * A[c][cc]
    return [A[i][k] / A[i][i] for i in range(k)]


def _rh(tf: float, tdf: float) -> float:
    t, td = (tf - 32) * 5 / 9, (tdf - 32) * 5 / 9
    es = 6.112 * math.exp(17.67 * t / (t + 243.5))
    e = 6.112 * math.exp(17.67 * td / (td + 243.5))
    return max(1.0, min(100.0, 100 * e / es))


class Downscaler:
    """Built once per NBM fetch from its grid box and the cells' terrain heights."""

    def __init__(self, nbm: Dict[str, Any], terrain: Dict[str, Optional[dict]], to_steps):
        box = nbm.get("box") or {}
        self.cycle = nbm["cycle_utc"]
        self.rows = box.get("rows") or {}
        self.ll = box.get("latlon") or []
        self.z: List[Optional[float]] = []
        for a, b in self.ll:
            t = terrain.get(f"{a:.4f},{b:.4f}") if terrain else None
            self.z.append(t.get("elevation_ft") if t else None)
        self.xy = [_xy(a, b) for a, b in self.ll]
        self.xc = [_cross(*p) for p in self.xy]
        self.to_steps = to_steps
        self._steps: Dict[int, List[Dict[str, Any]]] = {}

    @property
    def ok(self) -> bool:
        return bool(self.ll) and sum(1 for v in self.z if v is not None) >= 8 and bool(self.rows)

    def _point_steps(self, i: int, start: datetime) -> List[Dict[str, Any]]:
        if i not in self._steps:
            rows_i = {fh: {f: (vals[i] if i < len(vals) else None) for f, vals in r.items()} for fh, r in self.rows.items()}
            self._steps[i] = self.to_steps(self.cycle, rows_i, self.z[i] or 0, start)
        return self._steps[i]

    def adjust(self, lat: float, lon: float, elev_ft: float, start: datetime) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        tx, ty = _xy(lat, lon)
        dist = [math.hypot(p[0] - tx, p[1] - ty) for p in self.xy]
        valid = [i for i in range(len(self.ll)) if self.z[i] is not None]
        g = min(valid, key=lambda i: dist[i])
        nb = [i for i in valid if dist[i] <= RADIUS_KM]
        w = [math.exp(-(dist[i] / SIGMA_KM) ** 2) for i in nb]
        zg = self.z[g]
        zmin, zmax = min(self.z[i] for i in nb), max(self.z[i] for i in nb)
        z_eff = max(zmin - MAX_EXTRAP_FT, min(zmax + MAX_EXTRAP_FT, elev_ft))
        dz = (z_eff - zg) / 1000.0
        dx = _cross(tx, ty) - self.xc[g]
        Xz = [[1.0, (self.z[i] - zg) / 1000.0] for i in nb]
        Xzx = [[1.0, (self.z[i] - zg) / 1000.0, self.xc[i] - self.xc[g]] for i in nb]
        series = {i: self._point_steps(i, start) for i in nb}
        base = series[g]
        n = min(len(s) for s in series.values())
        out, lapses = [], []
        cum = {"snow": {i: 0.0 for i in nb}, "liq": {i: 0.0 for i in nb}}
        prev_c, prev_p = 0.0, 0.0
        for k in range(n):
            x0 = dict(base[k])
            for i in nb:
                cum["snow"][i] = series[i][k].get("cumulative_snow_inches") or 0.0
                cum["liq"][i] += series[i][k].get("precip_in") or 0.0
            # temperature and dew point (elevation only)
            t_ok = [i for i in nb if series[i][k].get("temp_f") is not None]
            if len(t_ok) >= 6 and x0.get("temp_f") is not None:
                cf = wls([Xz[nb.index(i)] for i in t_ok], [series[i][k]["temp_f"] for i in t_ok], [w[nb.index(i)] for i in t_ok])
                if cf:
                    b = max(LAPSE_BOUNDS_F_PER_KFT[0], min(LAPSE_BOUNDS_F_PER_KFT[1], cf[1]))
                    lapses.append(b)
                    x0["temp_f"] = round(x0["temp_f"] + b * dz, 1)
            d_ok = [i for i in nb if series[i][k].get("dew_point_f") is not None]
            if len(d_ok) >= 6 and x0.get("dew_point_f") is not None:
                cf = wls([Xz[nb.index(i)] for i in d_ok], [series[i][k]["dew_point_f"] for i in d_ok], [w[nb.index(i)] for i in d_ok])
                if cf:
                    b = max(-10.0, min(10.0, cf[1]))
                    x0["dew_point_f"] = round(min(x0.get("temp_f", 999), x0["dew_point_f"] + b * dz), 1)
            if x0.get("temp_f") is not None and x0.get("dew_point_f") is not None:
                x0["dew_point_depression_f"] = round(x0["temp_f"] - x0["dew_point_f"], 1)
                x0["relative_humidity_pct"] = round(_rh(x0["temp_f"], x0["dew_point_f"]))
            # snow/liquid ratio (elevation only)
            s_ok = [i for i in nb if series[i][k].get("slr")]
            slr_t = x0.get("slr")
            if len(s_ok) >= 6 and slr_t:
                cf = wls([Xz[nb.index(i)] for i in s_ok], [series[i][k]["slr"] for i in s_ok], [w[nb.index(i)] for i in s_ok])
                if cf:
                    slr_t = max(1.0, slr_t + cf[1] * dz)
                    x0["slr"] = round(slr_t, 1)
            # cumulative precipitation and snowfall (elevation + cross-crest), non-decreasing
            vals = []
            for key in ("liq", "snow"):
                ys = [cum[key][i] for i in nb]
                cf = wls(Xzx, ys, w) if max(ys) > 0 else None
                v = cum[key][g] + ((cf[1] * dz + cf[2] * dx) if cf else 0.0)
                vals.append(max(0.0, v))
            c_p = max(prev_p, vals[0])
            c_s = max(prev_c, vals[1])
            liq, snow = c_p - prev_p, c_s - prev_c
            prev_p, prev_c = c_p, c_s
            x0["precip_in"] = round(liq, 3)
            x0["snowfall_rate_in_hr"] = x0["model_snowfall_in_hr"] = round(snow, 2)
            x0["cumulative_snow_inches"] = x0["model_cumulative_inches"] = round(c_s, 2)
            if liq >= 0.004:
                frac = max(0.0, min(1.0, snow / (liq * slr_t))) if slr_t else x0.get("snow_fraction")
                x0["snow_fraction"] = round(frac, 2) if frac is not None else None
                x0["snow_factor"] = round(snow / liq, 2)
                ph = "snow" if frac is None or frac >= 0.9 else ("rain" if frac <= 0.1 else "mix")
                x0["precip_phase"] = ph
                x0["precip_phase_label"] = {"snow": "Snow", "mix": "Rain/snow", "rain": "Rain"}[ph]
            elif x0.get("snow_level_ft") is not None and x0.get("precip_phase") != "dry":
                x0["snow_fraction"] = 1.0 if elev_ft >= x0["snow_level_ft"] else 0.0
            x0["elevation_adjusted"] = True
            out.append(x0)
        g_snow = (base[n - 1].get("cumulative_snow_inches") or 0.0) if n else 0.0
        g_liq = sum(s.get("precip_in") or 0 for s in base[:n])
        lap_sorted = sorted(lapses)
        diag = {
            "method": "NBM local regression on terrain height (per hour), nearest cell moved to the tier elevation",
            "grid_lat": self.ll[g][0], "grid_lon": self.ll[g][1], "grid_elevation_ft": round(zg),
            "target_elevation_ft": round(elev_ft), "dz_ft": round(elev_ft - zg),
            "dz_used_ft": round(z_eff - zg), "neighbors": len(nb),
            "neighbor_elevation_ft": [round(zmin), round(zmax)],
            "extrapolation_ft": round(max(0.0, elev_ft - zmax, zmin - elev_ft)),
            "lapse_f_per_kft": {"median": round(lap_sorted[len(lap_sorted) // 2], 2),
                                "p10": round(lap_sorted[len(lap_sorted) // 10], 2),
                                "p90": round(lap_sorted[(9 * len(lap_sorted)) // 10], 2)} if lap_sorted else None,
            "snow_total_grid_in": round(g_snow, 1), "snow_total_adjusted_in": round(prev_c, 1),
            "liquid_total_grid_in": round(g_liq, 2), "liquid_total_adjusted_in": round(prev_p, 2),
            "hours": n,
        }
        return out, diag

    def regress_values(self, values: Dict[int, float], lat: float, lon: float, elev_ft: float) -> Optional[Dict[str, Any]]:
        """Same regression for a single field given at some box cells (e.g. NWS gridded snowfall)."""
        tx, ty = _xy(lat, lon)
        pts = [i for i in values if self.z[i] is not None and values[i] is not None and math.hypot(self.xy[i][0] - tx, self.xy[i][1] - ty) <= RADIUS_KM]
        if len(pts) < 6:
            return None
        dist = {i: math.hypot(self.xy[i][0] - tx, self.xy[i][1] - ty) for i in pts}
        g = min(pts, key=lambda i: dist[i])
        zg = self.z[g]
        zmin, zmax = min(self.z[i] for i in pts), max(self.z[i] for i in pts)
        z_eff = max(zmin - MAX_EXTRAP_FT, min(zmax + MAX_EXTRAP_FT, elev_ft))
        X = [[1.0, (self.z[i] - zg) / 1000.0, self.xc[i] - self.xc[g]] for i in pts]
        cf = wls(X, [values[i] for i in pts], [math.exp(-(dist[i] / SIGMA_KM) ** 2) for i in pts])
        if not cf:
            return None
        v = values[g] + cf[1] * (z_eff - zg) / 1000.0 + cf[2] * (_cross(tx, ty) - self.xc[g])
        return {"value": round(max(0.0, v), 1), "cell_value": round(values[g], 1), "cell_elevation_ft": round(zg),
                "slope_per_kft": round(cf[1], 2), "cells": len(pts), "extrapolation_ft": round(max(0.0, elev_ft - zmax, zmin - elev_ft))}
