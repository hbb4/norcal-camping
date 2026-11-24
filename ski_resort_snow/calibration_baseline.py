#!/usr/bin/env python3
"""Baseline scores for NBM at the SNOTEL sites (TUNING_PLAN.md step 5).

    python3 calibration_baseline.py            # all storm-day cycles on disk
    python3 calibration_baseline.py --md       # also write data/tuning/reports/nbm_baseline.md

For every archived day-1 NBM cycle (nbm_archive_sync.py fetch) and each of the seven SNOTEL
sites, two NBM values are scored against what the site measured over the storm-day (12Z-12Z):

  raw       the NBM cell nearest the site
  adjusted  the live method (nbm_downscale.py): a distance-weighted line through the cells
            within 7 km (elevation, plus distance across the crest for precipitation and
            snowfall), evaluated at the site's own height and position

  liquid    sum of the four 6 h NBM totals  vs  the pillow's snow-water gain (and the gauge)
  snowfall  sum of the four 6 h NBM snowfall totals  vs  the snow-depth gain (settling makes the
            depth gain smaller than new snow, so this is a lower bound, not truth)
  temp      2 m temperature at 18Z, 00Z, 06Z and 12Z  vs  the site's air temperature

Liquid is also scored on cold days only (site air temperature stays below 34 F), where the pillow
gain is snowfall rather than rain or melt. Rain-on-snow days at a site are left out at that site.
Results are given overall, per site and per NBM version.
"""

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from collectors.nbm_downscale import wls, _xy, _cross, RADIUS_KM, SIGMA_KM, MAX_EXTRAP_FT, LAPSE_BOUNDS_F_PER_KFT  # noqa: E402

TUNING = BASE_DIR / "data" / "tuning"
CYCLES = TUNING / "nbm" / "cycles"
TERRAIN = TUNING / "nbm" / "terrain.json"
STATIONS = TUNING / "nrcs" / "stations.json"
STORM_DAYS = TUNING / "storm_days.json"
REPORT_DIR = TUNING / "reports"
PST = timezone(timedelta(hours=-8))
MM_TO_IN, M_TO_IN = 1 / 25.4, 39.3701


def k_to_f(k):
    return None if k is None else (k - 273.15) * 1.8 + 32


class Box:
    """Grid cells of one cycle file with their terrain heights and flat coordinates."""

    def __init__(self, box, terrain):
        self.ll = box["latlon"]
        self.z = [(terrain.get(f"{a:.4f},{b:.4f}") or {}).get("elevation_ft") for a, b in self.ll]
        self.xy = [_xy(a, b) for a, b in self.ll]
        self.xc = [_cross(*p) for p in self.xy]

    def neighbors(self, lat, lon):
        tx, ty = _xy(lat, lon)
        d = [math.hypot(p[0] - tx, p[1] - ty) for p in self.xy]
        valid = [i for i in range(len(self.ll)) if self.z[i] is not None]
        g = min(valid, key=lambda i: d[i])
        nb = [i for i in valid if d[i] <= RADIUS_KM]
        return g, nb, [math.exp(-(d[i] / SIGMA_KM) ** 2) for i in nb], _cross(tx, ty)

    def estimate(self, vals, lat, lon, elev_ft, cross=True, lapse_clamp=False):
        """(raw nearest-cell value, adjusted value) of one field at a point."""
        g, nb, w, xt = self.neighbors(lat, lon)
        raw = vals[g]
        ok = [k for k, i in enumerate(nb) if vals[i] is not None]
        if raw is None or len(ok) < 6:
            return raw, None
        nb2, w2 = [nb[k] for k in ok], [w[k] for k in ok]
        zg = self.z[g]
        zmin, zmax = min(self.z[i] for i in nb2), max(self.z[i] for i in nb2)
        z_eff = max(zmin - MAX_EXTRAP_FT, min(zmax + MAX_EXTRAP_FT, elev_ft))
        X = [[1.0, (self.z[i] - zg) / 1000.0] + ([self.xc[i] - self.xc[g]] if cross else []) for i in nb2]
        cf = wls(X, [vals[i] for i in nb2], w2)
        if not cf:
            return raw, None
        b = cf[1]
        if lapse_clamp:
            b = max(LAPSE_BOUNDS_F_PER_KFT[0], min(LAPSE_BOUNDS_F_PER_KFT[1], b))
        adj = cf[0] + b * (z_eff - zg) / 1000.0 + (cf[2] * (xt - self.xc[g]) if cross else 0.0)
        return raw, adj


def load_tobs(code):
    rows = {}
    for f in sorted((TUNING / "nrcs" / code).glob("WY*.csv")):
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                rows[r["time_pst"]] = r
    return rows


def tobs_at(rows, t_utc):
    r = rows.get(t_utc.astimezone(PST).strftime("%Y-%m-%d %H:%M"))
    if not r or r.get("tobs_qc") == "S" or t_utc.astimezone(PST).hour == 0:
        return None
    try:
        return float(r["tobs_f"])
    except (TypeError, ValueError):
        return None


def collect():
    terrain = json.loads(TERRAIN.read_text()) if TERRAIN.exists() else {}
    sites = json.loads(STATIONS.read_text())["sites"]
    days = {d["date"]: d for d in json.loads(STORM_DAYS.read_text())["days"]}
    tobs = {s["cdec"]: load_tobs(s["cdec"]) for s in sites}
    recs = []
    for f in sorted(CYCLES.glob("nbm_*.json")):
        c = json.loads(f.read_text())
        cyc = datetime.fromisoformat(c["cycle_utc"].replace("Z", "+00:00"))
        if cyc.hour != 12:
            continue
        day = cyc.date().isoformat()
        sd = days.get(day)
        rows = c.get("rows") or {}
        if not sd or not c.get("box") or not all(str(h) in rows for h in (6, 12, 18, 24)):
            continue
        box = Box(c["box"], terrain)
        n = len(box.ll)

        def total(field, scale):
            out = []
            for i in range(n):
                v = [(rows[str(h)].get(field) or [None] * n)[i] for h in (6, 12, 18, 24)]
                out.append(None if any(x is None for x in v) else sum(v) * scale)
            return out

        liq, snow = total("apcp_6h", MM_TO_IN), total("asnow_6h", M_TO_IN)
        for s in sites:
            code = s["cdec"]
            ob = (sd.get("obs") or {}).get(code) or {}
            lat, lon, z = s["latitude"], s["longitude"], s["elevation"]
            l_raw, l_adj = box.estimate(liq, lat, lon, z, cross=True)
            s_raw, s_adj = box.estimate(snow, lat, lon, z, cross=True)
            temps = []
            for h in (6, 12, 18, 24):
                tk = [k_to_f(v) for v in (rows[str(h)].get("tmp_k") or [None] * n)]
                t_raw, t_adj = box.estimate(tk, lat, lon, z, cross=False, lapse_clamp=True)
                temps.append((tobs_at(tobs[code], cyc + timedelta(hours=h)), t_raw, t_adj))
            recs.append({"date": day, "version": c.get("nbm_version"), "site": code, "elev": z,
                         "liq_raw": l_raw, "liq_adj": max(0.0, l_adj) if l_adj is not None else None,
                         "snow_raw": s_raw, "snow_adj": max(0.0, s_adj) if s_adj is not None else None,
                         "swe_gain": ob.get("swe_gain_in"), "gauge": ob.get("precip_gain_in"), "depth_gain": ob.get("depth_gain_in"),
                         "tmax": ob.get("tobs_max_f"), "ros": ob.get("rain_on_snow"), "temps": temps})
    return recs


def stats(pairs):
    """pairs: [(forecast, observed)] -> n, bias, MAE."""
    p = [(f, o) for f, o in pairs if f is not None and o is not None]
    if not p:
        return {"n": 0}
    e = [f - o for f, o in p]
    return {"n": len(p), "bias": round(sum(e) / len(e), 2), "mae": round(sum(abs(x) for x in e) / len(e), 2)}


def scores(recs):
    def block(rs):
        liq_ok = [r for r in rs if not r["ros"] and r["swe_gain"] is not None and r["swe_gain"] >= 0]
        cold = [r for r in liq_ok if r["tmax"] is not None and r["tmax"] < 34]
        out = {}
        for key, sel, obs in (("liquid vs pillow, all", liq_ok, "swe_gain"), ("liquid vs pillow, cold days", cold, "swe_gain"),
                              ("liquid vs gauge", rs, "gauge"), ("snowfall vs depth gain", rs, "depth_gain")):
            fld = "liq" if key.startswith("liquid") else "snow"
            out[key] = {"raw": stats([(r[f"{fld}_raw"], r[obs]) for r in sel]), "adjusted": stats([(r[f"{fld}_adj"], r[obs]) for r in sel])}
        out["temperature"] = {"raw": stats([(t_raw, ob) for r in rs for ob, t_raw, _ in r["temps"]]),
                              "adjusted": stats([(t_adj, ob) for r in rs for ob, _, t_adj in r["temps"]])}
        return out
    res = {"all": block(recs)}
    for key in sorted({r["site"] for r in recs}):
        res[f"site {key}"] = block([r for r in recs if r["site"] == key])
    for v in sorted({r["version"] for r in recs if r["version"]}):
        res[f"NBM v{v}"] = block([r for r in recs if r["version"] == v])
    return res


def fmt(res, n_days):
    lines = [f"NBM day-1 baseline: {n_days} storm-days. Error = NBM minus observed; bias / MAE (n). Units: in, temperature F.", ""]
    for group, blk in res.items():
        lines.append(f"{group}")
        for key, v in blk.items():
            r, a = v["raw"], v["adjusted"]
            if not r.get("n"):
                continue
            skill = (1 - a["mae"] / r["mae"]) * 100 if r.get("mae") and a.get("n") else None
            lines.append(f"  {key:26} raw {r['bias']:+6.2f} / {r['mae']:5.2f} (n {r['n']:4})   adjusted {a.get('bias', 0):+6.2f} / {a.get('mae', 0):5.2f}"
                         + (f"   MAE change {-skill:+.0f}%" if skill is not None else ""))
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", action="store_true", help="write data/tuning/reports/nbm_baseline.md and .json")
    a = ap.parse_args()
    if not any(CYCLES.glob("nbm_*.json")):
        print("No NBM cycles yet. Run: python3 nbm_archive_sync.py fetch")
        return 1
    recs = collect()
    days = len({r["date"] for r in recs})
    res = scores(recs)
    text = fmt(res, days)
    print(text)
    if a.md:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "nbm_baseline.json").write_text(json.dumps({"created": datetime.now(timezone.utc).isoformat(), "storm_days": days, "scores": res}, indent=1))
        (REPORT_DIR / "nbm_baseline.md").write_text("# NBM baseline at SNOTEL sites\n\n```\n" + text + "\n```\n")
        print(f"Saved {REPORT_DIR / 'nbm_baseline.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
