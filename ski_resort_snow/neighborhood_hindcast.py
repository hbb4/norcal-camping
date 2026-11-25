#!/usr/bin/env python3
"""Does using the cells around a pillow beat the single nearest cell? (interpolation and a
precipitation elevation shift for the Open-Meteo models)

    python3 neighborhood_hindcast.py fetch --plan          # how many requests, nothing fetched
    python3 neighborhood_hindcast.py fetch                 # cells around SQV and WC3, WY2026-WY2027
    python3 neighborhood_hindcast.py fetch --seasons 2025,2026,2027 --points 9
    python3 neighborhood_hindcast.py score [--md]          # compare the estimates below

fetch: for every blend member, a 3x3 (or plus-shaped, --points 5) set of points around each pillow,
spaced one model grid step apart, so that Open-Meteo returns the neighboring cells. Each request uses
elevation=nan, so the response carries that cell's own terrain height. Points that land in the same
cell are fetched once. Cached in data/tuning/hindcast_nbr/ (rerun to resume; finished seasons are
never fetched again). Open-Meteo counts a request covering a ~6-month season as about 13 calls, so
the default (6 models x 2 pillows x 9 points x 2 seasons) is about 2,800 calls; the free limit is
10,000 a day, shared with the dashboard's own refresh.

score: for each model, cold 12Z-12Z days and whole storms at the pillow (same rules as
skill_report.py), four estimates of the pillow's precipitation:
  center      the cell Open-Meteo picks for the pillow itself (what the hindcast and blends use now)
  idw         inverse-distance mean of the cells around it
  elev-match  the cell whose terrain height is closest to the pillow's
  elev-line   a distance-weighted fit of the day's precipitation against cell height and distance
              across the Sierra crest (when 5+ cells; height only with 3-4), evaluated at the pillow:
              an elevation shift for precipitation from the model's own field (the NBM method)
Each is scored raw and bias-corrected (multiplier fitted on the other seasons).
"""

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import blend_weights as bw  # noqa: E402
import skill_report as sr  # noqa: E402
from collectors import precip_shift as ps  # noqa: E402

CACHE = BASE_DIR / "data" / "tuning" / "hindcast_nbr"
REPORT_DIR = BASE_DIR / "data" / "tuning" / "reports"
M_TO_FT = 3.28084
GRID_STEP = ps.GRID_STEP_DEG   # approximate grid step (degrees) used to reach the neighboring cell of each model
SITE_ELEV_FT = {"SQV": 8010, "WC3": 6750}
LAKE_TAHOE_FT = ps.LAKE_TAHOE_FT   # water cells over the lake are reported at 0 ft; the models' surface there is the lake


def offsets(points):
    if points == 5:
        return [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
    return [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)]


def season_range(wy):
    start = f"{wy - 1}-11-01"
    end = f"{wy}-04-30"
    today = datetime.now(timezone.utc).date()
    if end >= today.isoformat():
        end = (today - timedelta(days=2)).isoformat()
    return start, end


def fetch_point(om, lat, lon, start, end):
    q = {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "elevation": "nan", "hourly": "precipitation", "models": om,
         "start_date": start, "end_date": end, "timezone": "GMT", "precipitation_unit": "inch"}
    req = urllib.request.Request(f"{bw.HINDCAST_URL}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "SierraSnowDashboard/3.0 (neighborhood hindcast)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("error"):
                raise RuntimeError(d.get("reason"))
            h = d.get("hourly", {})
            return {"cell_lat": d.get("latitude"), "cell_lon": d.get("longitude"), "cell_elev_m": d.get("elevation"),
                    "series": {t: v for t, v in zip(h.get("time", []), h.get("precipitation", []))}}
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def plan_or_fetch(seasons, points, do_fetch, models=None, sites=None, log=print):
    members = bw.member_models()
    models = models or list(members)
    sites = sites or list(bw.HINDCAST_SITES)
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = []
    for mid in models:
        om = members[mid]
        step = GRID_STEP.get(om, 0.1)
        for site in sites:
            lat, lon = bw.HINDCAST_SITES[site]
            for wy in seasons:
                start, end = season_range(wy)
                for i, j in offsets(points):
                    path = CACHE / f"{om}_{site}_{i:+d}{j:+d}_{start}_{end}.json"
                    if not path.exists():
                        todo.append((path, om, lat + i * step, lon + j * step / math.cos(math.radians(lat)), start, end))
    days = sum((date.fromisoformat(t[5]) - date.fromisoformat(t[4])).days + 1 for t in todo)
    calls = sum(max(1, math.ceil(((date.fromisoformat(t[5]) - date.fromisoformat(t[4])).days + 1) / 14)) for t in todo)
    log(f"{len(todo)} requests to make ({days} station-days, about {calls} Open-Meteo calls; free limit 10,000/day)")
    if not do_fetch:
        return 0
    for n, (path, om, la, lo, start, end) in enumerate(todo, 1):
        try:
            r = fetch_point(om, la, lo, start, end)
        except Exception as e:
            log(f"  {path.name}: {type(e).__name__}: {e} (rerun to retry)")
            continue
        path.write_text(json.dumps(r))
        if n % 10 == 0 or n == len(todo):
            log(f"  {n}/{len(todo)} done")
        time.sleep(0.5)
    return 0


def load_cells(om, site):
    """{date-free cell key: {lat, lon, elev_ft, series}} merged across seasons; one entry per distinct cell."""
    cells = {}
    for f in sorted(CACHE.glob(f"{om}_{site}_*.json")):
        d = json.loads(f.read_text())
        key = (round(d["cell_lat"], 3), round(d["cell_lon"], 3))
        elev, lake = ps.cell_height_ft(d.get("cell_elev_m"))      # Lake Tahoe cells come back as water at 0 ft
        c = cells.setdefault(key, {"lat": d["cell_lat"], "lon": d["cell_lon"], "elev_ft": elev,
                                   "lake": lake, "center": False, "series": {}})
        c["center"] = c["center"] or "_+0+0_" in f.name
        c["series"].update(d["series"])
    return cells


def estimates_for_day(cells, site, t0):
    """Four estimates of the 12Z-12Z precipitation at the pillow from the cells around it."""
    lat, lon = bw.HINDCAST_SITES[site]
    z_site = SITE_ELEV_FT[site]
    vals = []
    for c in cells.values():
        v = [c["series"].get((t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")) for k in range(1, 25)]
        if any(x is None for x in v):
            continue
        dkm = math.hypot((c["lat"] - lat) * 111.0, (c["lon"] - lon) * 111.0 * math.cos(math.radians(lat)))
        vals.append({"p": sum(v), "d": dkm, "z": c["elev_ft"], "center": c["center"], "lat": c["lat"], "lon": c["lon"]})
    if not vals:
        return None
    center = next((x["p"] for x in vals if x["center"]), None)
    w = [1 / max(0.5, x["d"]) ** 2 for x in vals]
    idw = sum(wi * x["p"] for wi, x in zip(w, vals)) / sum(w)
    withz = [x for x in vals if x["z"] is not None]
    match = min(withz, key=lambda x: abs(x["z"] - z_site))["p"] if withz else None
    # elevation line: the shared method the live forecast uses (collectors/precip_shift.py)
    wts, _ = ps.line_weights([{"lat": x["lat"], "lon": x["lon"], "z": x["z"]} for x in vals], lat, lon, z_site)
    line = ps.estimate([x["p"] for x in vals], wts) if wts else None
    return {"center": center, "idw": idw, "elev-match": match, "elev-line": line}


VARIANTS = ["center", "idw", "elev-match", "elev-line"]


def collect():
    """Per model: cold site-day records with the four estimates, and a line describing the cells."""
    members = bw.member_models()
    out = {}
    for mid, om in members.items():
        recs, cell_info = [], []
        for site in bw.HINDCAST_SITES:
            cells = load_cells(om, site)
            if not cells:
                continue
            zs = [c["elev_ft"] for c in cells.values() if c["elev_ft"] is not None]
            n_lake = sum(c["lake"] for c in cells.values())
            cell_info.append(f"{site}: {len(cells)} cells, {min(zs):,.0f}-{max(zs):,.0f} ft (pillow {SITE_ELEV_FT[site]:,} ft)"
                             + (f", {n_lake} lake" if n_lake else ""))
            rows = bw.load_snotel(site)
            days = sorted({t[:10] for c in cells.values() for t in c["series"]})
            for d in days:
                day = date.fromisoformat(d)
                t0 = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
                a, b, tmax = bw.swe_at(rows, t0), bw.swe_at(rows, t0 + timedelta(hours=24)), bw.max_temp(rows, t0, t0 + timedelta(hours=24))
                if a is None or b is None or tmax is None or tmax >= sr.COLD_F:
                    continue
                est = estimates_for_day(cells, site, t0)
                if not est or any(v is None for v in est.values()):
                    continue
                recs.append({"site": site, "day": day, "wy": sr.water_year(day), "obs": max(0.0, b - a), "fc": est})
        if recs:
            out[mid] = {"om": om, "recs": recs, "cells": "; ".join(cell_info)}
    return out


def blend_records(data, models, variant):
    """Site-days where every model has the estimate, with fc = {model: that model's estimate}."""
    by = {}
    for mid in models:
        for r in data[mid]["recs"]:
            by.setdefault((r["site"], r["day"]), {"site": r["site"], "day": r["day"], "wy": r["wy"], "obs": r["obs"], "fc": {}})["fc"][mid] = r["fc"][variant]
    return [r for r in by.values() if all(m in r["fc"] for m in models)]


def blend_table(data, models, storms):
    """Equal-weight blends of the models from the single cell and from the elevation line, raw and corrected."""
    rows, n = {}, 0
    for v in ("center", "elev-line"):
        recs = blend_records(data, models, v)
        n = len(recs)
        srecs = sr.storm_records(recs, storms, models)
        site = sr.evaluate(recs, srecs, models)
        pooled = sr.evaluate(recs, srecs, models, pool_sites=True)
        if not site:
            return None, n
        name = "single cell" if v == "center" else "elevation line"
        rows[f"{name}, raw"] = site["blends"]["equal raw"]
        rows[f"{name} x site mult."] = site["blends"]["equal corrected"]
        rows[f"{name} x pooled mult."] = pooled["blends"]["equal corrected"]
    return rows, n


def residuals(data, pool_sites=True):
    """Residual multiplier per model after the elevation shift, fitted on all seasons (what `fit` writes)."""
    out = {}
    for mid, d in data.items():
        recs = [{**r, "fc": {mid: r["fc"]["elev-line"]}} for r in d["recs"]]
        f = sr.factors(recs, [mid], pool_sites)
        out[mid] = {site: round(v, 3) for (m, site), v in f.items()}
    return out


def score(md=False):
    lines = ["Neighborhood test: cold 12Z-12Z days and whole storms at SQV and WC3; scores on held-out seasons.",
             "MAE / bias in inches; raw and bias-corrected (multiplier fitted on the other seasons: per pillow, or pooled over both).",
             f"Lake Tahoe cells (reported at 0 ft) are taken at the lake surface, {LAKE_TAHOE_FT:,} ft.", ""]
    storms = sr.storms_from(json.loads(sr.STORM_DAYS.read_text())["days"]) if sr.STORM_DAYS.exists() else []
    data = collect()
    for mid, d in data.items():
        recs = d["recs"]
        srecs = sr.storm_records(recs, storms, VARIANTS)
        res = sr.evaluate(recs, srecs, VARIANTS)
        pooled = sr.evaluate(recs, srecs, VARIANTS, pool_sites=True)
        lines.append(f"== {mid} ({d['om']}); {len(recs)} cold site-days; {d['cells']}")
        if not res:
            lines.append("  one season only: fetch more seasons to score out of sample\n")
            continue
        lines.append(f"  {'estimate':12} {'raw day MAE':>12} {'bias':>7} {'raw storm MAE':>14} {'bias':>7}   {'corr. day MAE':>14} {'corr. storm MAE':>16}   {'pooled day':>10} {'pooled storm':>12} {'bias':>7}")
        f = lambda x: "  -  " if x is None else f"{x:.2f}" if x >= 0 else f"{x:+.2f}"
        for v in VARIANTS:
            r, c, q = res["members_raw"][v], res["members_corrected"][v], pooled["members_corrected"][v]
            lines.append(f"  {v:12} {f(r['day_mae']):>12} {f(r['day_bias']):>7} {f(r['storm_mae']):>14} {f(r['storm_bias']):>7}   "
                         f"{f(c['day_mae']):>14} {f(c['storm_mae']):>16}   {f(q['day_mae']):>10} {f(q['storm_mae']):>12} {f(q['storm_bias']):>7}")
        lines.append("")
    if not data:
        lines.append("No neighborhood data yet. Run: python3 neighborhood_hindcast.py fetch --plan, then fetch.")
    else:
        six = [m for m in bw.member_models() if m in data]
        five = [m for m in six if m != "aifs"]
        for title, models in ((f"five members, no AIFS (longer record)", five), (f"all {len(six)} members (common days)", six)):
            rows, n = blend_table(data, models, storms)
            if rows:
                lines.append(sr.fmt_table(f"== Equal blends, {title}: {n} cold site-days", rows))
                lines.append("")
        res_pool, res_site = residuals(data, True), residuals(data, False)
        lines.append("Residual multipliers after the elevation shift, all seasons (pooled over both pillows; per pillow in brackets):")
        for mid in data:
            lines.append(f"  {mid:12} {next(iter(res_pool[mid].values())):.2f}   [" + ", ".join(f"{s} {v:.2f}" for s, v in sorted(res_site[mid].items())) + "]")
    out = "\n".join(lines)
    print(out)
    if md:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "neighborhood.md").write_text("# Neighborhood test\n\n```\n" + out + "\n```\n")
        print(f"Saved {REPORT_DIR / 'neighborhood.md'}")
    return 0


CONFIG = BASE_DIR / "config" / "sources.json"
RESIDUAL_BOUNDS = [0.5, 2.0]
CORRECTED_BLEND = {
    "id": "blend_corrected", "label": "Corrected blend",
    "members": {"ecmwf_hres": 1, "aifs": 1, "hrrr_gfs": 1, "rrfs": 1, "icon": 1, "ukmo": 1, "gem": 1},
    "precip_correction": True, "profile_from": "ecmwf_hres", "min_weight_share": 0.5,
}


def fit(apply=False):
    """Residual multiplier per model after the elevation shift (pooled over both pillows, all seasons)."""
    storms = sr.storms_from(json.loads(sr.STORM_DAYS.read_text())["days"]) if sr.STORM_DAYS.exists() else []
    data = collect()
    if not data:
        print("No neighborhood data yet. Run: python3 neighborhood_hindcast.py fetch")
        return 1
    pooled = {mid: round(next(iter(v.values())), 2) for mid, v in residuals(data, True).items()}
    seasons = sorted({r["wy"] for d in data.values() for r in d["recs"]})
    five = [m for m in bw.member_models() if m in data and m != "aifs"]
    rows, n = blend_table(data, five, storms)
    pick = lambda r: {"day_mae": round(r["day_mae"], 3), "day_bias": round(r["day_bias"], 3), "storm_mae": round(r["storm_mae"], 3),
                      "storm_bias": round(r["storm_bias"], 3), "day_csi": round(r["day_cat"]["csi"], 2), "day_pod": round(r["day_cat"]["pod"], 2),
                      "day_far": round(r["day_cat"]["far"], 2)}
    # each model alone, held-out seasons: own cell raw vs elevation line x pooled multiplier
    keys = ("day_mae", "day_bias", "storm_mae", "storm_bias")
    loso_m = {}
    for mid, d in data.items():
        ev = sr.evaluate(d["recs"], sr.storm_records(d["recs"], storms, VARIANTS), VARIANTS, pool_sites=True)
        if ev:
            a_, b_ = ev["members_raw"]["center"], ev["members_corrected"]["elev-line"]
            loso_m[mid] = {"cold_site_days": len(d["recs"]), "storms": a_["n_storms"],
                           "own_cell": {k: round(a_[k], 3) for k in keys if a_[k] is not None},
                           "corrected": {k: round(b_[k], 3) for k in keys if b_[k] is not None}}
    loso = {"members": five, "cold_site_days": n,
            **{k: pick(rows[k]) for k in ("single cell, raw", "elevation line, raw", "elevation line x pooled mult.")}} if rows else None
    block = {
        "method": ("elevation line from each model's 3x3 neighborhood of grid cells (distance-weighted fit against cell height, plus distance "
                   "across the crest), evaluated at the tier height (at most 1,000 ft beyond the cells), then one residual multiplier per model"),
        "residual": pooled, "residual_bounds": RESIDUAL_BOUNDS,
        "fitted": {"created": datetime.now(timezone.utc).date().isoformat(), "script": "neighborhood_hindcast.py fit",
                   "seasons": f"WY{seasons[0]}-WY{seasons[-1]}", "pillows": list(bw.HINDCAST_SITES),
                   "cold_site_days": {mid: len(d["recs"]) for mid, d in data.items()},
                   "residual_by_pillow": residuals(data, False), "loso_equal_blend": loso, "loso_members": loso_m},
    }
    print(f"Residual multipliers after the elevation shift ({block['fitted']['seasons']}, pooled over {', '.join(bw.HINDCAST_SITES)}):")
    for mid, v in pooled.items():
        print(f"  {mid:12} {v:.2f}" + ("  (outside bounds, capped)" if not RESIDUAL_BOUNDS[0] <= v <= RESIDUAL_BOUNDS[1] else ""))
    if loso:
        a, b = loso["single cell, raw"], loso["elevation line x pooled mult."]
        print(f"Equal blend of {len(five)} members, held-out seasons ({n} cold site-days): storm MAE {a['storm_mae']:.2f} -> {b['storm_mae']:.2f} in, "
              f"day MAE {a['day_mae']:.2f} -> {b['day_mae']:.2f}, day POD {a['day_pod']:.2f} -> {b['day_pod']:.2f}")
    if not apply:
        print("Not applied (add --apply to write config/sources.json).")
        return 0
    d = json.loads(CONFIG.read_text())
    d["precip_correction"] = block
    blends = d.setdefault("blends", [])
    b = next((x for x in blends if x["id"] == CORRECTED_BLEND["id"]), None)
    if b is None:
        b = dict(CORRECTED_BLEND)
        at = next((i + 1 for i, x in enumerate(blends) if x["id"] == "blend"), len(blends))
        blends.insert(at, b)
    from collectors.open_meteo_client import MODELS
    names = {m["id"]: m["label"] for m in MODELS}
    r = ", ".join(f"{names.get(m, m)} {v:.2f}" for m, v in pooled.items())
    unfitted = [names.get(m, m) for m in b["members"] if m not in pooled]
    b["description"] = (f"Equal-weight mean of {len(b['members'])} single models with their precipitation corrected. Each model's precipitation at each tier "
                        "comes from a distance-weighted line through its own 3x3 neighborhood of grid cells against cell height (and distance "
                        "across the crest), evaluated at the tier's height but at most 1,000 ft above the highest cell, then times one residual "
                        f"multiplier per model ({r}) fitted against the SQV and WC3 pillows over {block['fitted']['seasons']} "
                        "(neighborhood_hindcast.py fit). Snow follows from the corrected liquid through each model's own snow fraction and SLR; "
                        "temperature, wind and the profile panels are the same as the Equal blend."
                        + (f" {', '.join(unfitted)}: no hindcast yet, so the elevation shift only (multiplier 1.0)." if unfitted else ""))
    b["weights_note"] = "precipitation elevation-shifted and bias-corrected"
    CONFIG.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    print("Applied to config/sources.json: precip_correction and blend_corrected (takes effect on the next data refresh)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "score", "fit"])
    ap.add_argument("--seasons", default="2026,2027", help="water years, e.g. 2025,2026,2027")
    ap.add_argument("--points", type=int, choices=[5, 9], default=9)
    ap.add_argument("--plan", action="store_true", help="fetch: only count the requests")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--apply", action="store_true", help="fit: write the multipliers and the corrected blend into config/sources.json")
    a = ap.parse_args()
    if a.command == "score":
        return score(a.md)
    if a.command == "fit":
        return fit(a.apply)
    from collectors import http_ssl
    http_ssl.install()
    seasons = [int(s) for s in a.seasons.split(",") if s.strip()]
    return plan_or_fetch(seasons, a.points, not a.plan)


if __name__ == "__main__":
    sys.exit(main())
