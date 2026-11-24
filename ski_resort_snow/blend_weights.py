#!/usr/bin/env python3
"""Skill weights for the model blends (TUNING_PLAN.md item 8).

    python3 nrcs_sync.py              # first: bring the SNOTEL hourly data up to date
    python3 blend_weights.py          # score each model and suggest weights
    python3 blend_weights.py --min-n 10 --write
    python3 blend_weights.py --hindcast --write   # fit now from Open-Meteo's archived forecasts (see below)

Every pipeline run archives each model's next 72 h at each tier (data/archive/models/, kept
45 days). This pairs the Palisades mid tier (8,010 ft) with the SQV SNOTEL pillow at the same
height: forecast liquid over a 24 h window against the pillow's snow-water gain over the same
window. Only cold windows count (SQV air temperature stays below 34 F), where the gain is new
snow rather than rain or melt; only wet windows count (either side >= 0.1 in). One snapshot per
day (the one closest to 12Z) is used, because snapshots 3 h apart forecast nearly the same
window. Windows: day 1 = hours 0-24 from the snapshot, day 2 = hours 24-48.

Suggested weight = 1 / MAE, scaled so the members average 1, per lead day; a model needs at
least --min-n wet windows on that day. Nothing is written to config/sources.json; --write saves
the suggestion to data/tuning/blend_weights.json for review.

--hindcast: instead of the live archive, use Open-Meteo's Historical Forecast API (the stitched
series of each model's most recent run, i.e. short-lead forecasts) at the SQV and WC3 pillows,
every November-April day from WY2023, 12Z-12Z precipitation against the pillow's snow-water gain,
same cold/wet rule. ECMWF AIFS starts in spring 2025, so weights for all six members come from the
common period (2025-03-01 on); the five-member result over the full period is shown as a check.
Downloads are cached in data/tuning/hindcast/ (one request per model, site and season).
"""

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE = BASE_DIR / "data" / "archive" / "models"
NRCS = BASE_DIR / "data" / "tuning" / "nrcs"
OUT = BASE_DIR / "data" / "tuning" / "blend_weights.json"
PST = timezone(timedelta(hours=-8))
LEADS = {"day 1": (0, 24), "day 2": (24, 48)}


def load_snotel(code="SQV", nrcs_dir=NRCS):
    rows = {}
    for f in sorted((Path(nrcs_dir) / code).glob("WY*.csv")):
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                rows[r["time_pst"]] = r
    return rows


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def swe_at(rows, t_utc):
    """Median of the raw hourly snow-water readings within 2 h of a time (suspect and 00:00 values skipped)."""
    vals = []
    for dh in range(-2, 3):
        t = (t_utc + timedelta(hours=dh)).astimezone(PST)
        r = rows.get(t.strftime("%Y-%m-%d %H:%M"))
        if not r or r.get("wteq_qc") == "S" or t.hour == 0:
            continue
        v = _num(r.get("wteq_in"))
        if v is not None:
            vals.append(v)
    return statistics.median(vals) if len(vals) >= 3 else None


def max_temp(rows, t0, t1):
    vals = []
    t = t0
    while t <= t1:
        r = rows.get(t.astimezone(PST).strftime("%Y-%m-%d %H:%M"))
        if r and r.get("tobs_qc") != "S":
            v = _num(r.get("tobs_f"))
            if v is not None:
                vals.append(v)
        t += timedelta(hours=1)
    return max(vals) if len(vals) >= 18 else None


def daily_snapshots(archive=ARCHIVE):
    """One archived snapshot per day: the one issued closest to 12Z."""
    best = {}
    for f in sorted(Path(archive).glob("models_*.json")):
        try:
            t = datetime.strptime(f.stem[7:], "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        key = t.date()
        if key not in best or abs(t.hour - 12) < abs(best[key][0].hour - 12):
            best[key] = (t, f)
    return [json.loads(f.read_text()) for _, (t, f) in sorted(best.items())]


def pairs(snapshots, rows, resort="palisades_tahoe", tier="mid", cold_f=34.0, wet_in=0.1):
    """{(model, lead): [(forecast liquid, observed snow-water gain)]} for cold, wet windows."""
    out = {}
    for snap in snapshots:
        for mid, mo in ((snap.get("resorts") or {}).get(resort) or {}).items():
            tl = (mo.get("tiers") or {}).get(tier)
            if not tl or not tl.get("start"):
                continue
            start = datetime.fromisoformat(tl["start"].replace("Z", "+00:00"))
            pr = tl.get("precip_in") or []
            for lead, (h0, h1) in LEADS.items():
                seg = pr[h0:h1]
                if len(seg) < h1 - h0 or any(v is None for v in seg):
                    continue
                t0, t1 = start + timedelta(hours=h0), start + timedelta(hours=h1)
                a, b, tmax = swe_at(rows, t0), swe_at(rows, t1), max_temp(rows, t0, t1)
                if a is None or b is None or tmax is None or tmax >= cold_f:
                    continue
                fc, ob = sum(seg), max(0.0, b - a)
                if fc >= wet_in or ob >= wet_in:
                    out.setdefault((mid, lead), []).append((fc, ob))
    return out


def suggest(pr, min_n=15):
    """Per lead: {model: {n, bias, mae, weight}}; weight None when the sample is too small."""
    res = {}
    for lead in LEADS:
        stats = {}
        for (mid, ld), v in pr.items():
            if ld != lead or mid.startswith("blend"):
                continue
            err = [f - o for f, o in v]
            stats[mid] = {"n": len(v), "bias": round(sum(err) / len(err), 3), "mae": round(sum(abs(e) for e in err) / len(err), 3)}
        ok = {m: s for m, s in stats.items() if s["n"] >= min_n and s["mae"] > 0}
        inv = {m: 1 / s["mae"] for m, s in ok.items()}
        mean = sum(inv.values()) / len(inv) if inv else None
        for m, s in stats.items():
            s["weight"] = round(inv[m] / mean, 2) if m in inv else None
        res[lead] = stats
    return res


HINDCAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
HINDCAST_DIR = BASE_DIR / "data" / "tuning" / "hindcast"
HINDCAST_SITES = {"SQV": (39.18986, -120.26576), "WC3": (39.13545, -120.21865)}
SEASONS = [(2023, "2022-11-01", "2023-04-30"), (2024, "2023-11-01", "2024-04-30"), (2025, "2024-11-01", "2025-04-30"),
           (2026, "2025-11-01", "2026-04-30"), (2027, "2026-11-01", None)]
COMMON_FROM = "2025-03-01"   # first full month of ECMWF AIFS in the archive


def member_models():
    sys.path.insert(0, str(BASE_DIR))
    from collectors.open_meteo_client import MODELS
    cfg = json.loads((BASE_DIR / "config" / "sources.json").read_text()).get("blends") or []
    members = next((b["members"] for b in cfg if b["id"] == "blend"), None) or {}
    return {m["id"]: m["om"] for m in MODELS if m["id"] in members and m["om"]}


def fetch_hindcast(om_id, site, lat, lon, start, end):
    """Hourly precipitation (in) {iso hour: value} from the Historical Forecast API, cached per model/site/season."""
    HINDCAST_DIR.mkdir(parents=True, exist_ok=True)
    path = HINDCAST_DIR / f"{om_id}_{site}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text())
    import urllib.parse
    import urllib.request
    q = {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "elevation": "nan", "hourly": "precipitation",
         "models": om_id, "start_date": start, "end_date": end, "timezone": "GMT", "precipitation_unit": "inch"}
    req = urllib.request.Request(f"{HINDCAST_URL}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "SierraSnowDashboard/3.0 (blend hindcast)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("error"):
        raise RuntimeError(d.get("reason"))
    h = d.get("hourly", {})
    out = {t: v for t, v in zip(h.get("time", []), h.get("precipitation", []))}
    if end and end < datetime.now(timezone.utc).date().isoformat():   # only finished seasons are cached
        path.write_text(json.dumps(out))
    return out


def hindcast_pairs(series_by_model, rows, days, cold_f=34.0, wet_in=0.1):
    """{model: [(day, forecast liquid, observed gain)]} for cold, wet 12Z-12Z windows.
    series: {model: {"YYYY-MM-DDTHH:00": preceding-hour precipitation}}; days: list of date objects."""
    out = {}
    for day in days:
        t0 = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=24)
        a, b, tmax = swe_at(rows, t0), swe_at(rows, t1), max_temp(rows, t0, t1)
        if a is None or b is None or tmax is None or tmax >= cold_f:
            continue
        ob = max(0.0, b - a)
        for mid, s in series_by_model.items():
            vals = [s.get((t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")) for k in range(1, 25)]   # 13Z ... 12Z
            if any(v is None for v in vals):
                continue
            fc = sum(vals)
            if fc >= wet_in or ob >= wet_in:
                out.setdefault(mid, []).append((day, fc, ob))
    return out


def score(pairs_by_model, min_n):
    stats = {}
    for mid, v in pairs_by_model.items():
        err = [f - o for _, f, o in v]
        stats[mid] = {"n": len(v), "bias": round(sum(err) / len(err), 3), "mae": round(sum(abs(e) for e in err) / len(err), 3)}
    ok = {m: s for m, s in stats.items() if s["n"] >= min_n and s["mae"] > 0}
    inv = {m: 1 / s["mae"] for m, s in ok.items()}
    mean = sum(inv.values()) / len(inv) if inv else None
    for m, s in stats.items():
        s["weight"] = round(inv[m] / mean, 2) if m in inv else None
    return stats


def run_hindcast(min_n, write):
    sys.path.insert(0, str(BASE_DIR))
    from collectors import http_ssl
    http_ssl.install()
    members = member_models()
    today = datetime.now(timezone.utc).date()
    all_pairs = {}
    for site, (lat, lon) in HINDCAST_SITES.items():
        rows = load_snotel(site)
        if not rows:
            print(f"No SNOTEL data for {site}. Run: python3 nrcs_sync.py")
            return 1
        for wy, start, end in SEASONS:
            end = end or (today - timedelta(days=2)).isoformat()
            if end < start:
                continue
            series = {}
            for mid, om in members.items():
                try:
                    series[mid] = fetch_hindcast(om, site, lat, lon, start, end)
                except Exception as e:
                    print(f"  {mid} {site} WY{wy}: {type(e).__name__}: {e}")
            d0, d1 = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date() - timedelta(days=1)
            days = [d0 + timedelta(days=k) for k in range((d1 - d0).days + 1)]
            for mid, v in hindcast_pairs(series, rows, days).items():
                all_pairs.setdefault(mid, []).extend((site,) + x for x in v)
    common_from = datetime.fromisoformat(COMMON_FROM).date()
    # common period: only days every member has
    by_key = {}
    for mid, v in all_pairs.items():
        for site, day, f, o in v:
            if day >= common_from:
                by_key.setdefault((site, day), {})[mid] = (f, o)
    common = {mid: [(day, k[mid][0], k[mid][1]) for (site, day), k in by_key.items() if len(k) == len(members)] for mid in members}
    full5 = {mid: [(d, f, o) for _, d, f, o in v] for mid, v in all_pairs.items() if mid != "aifs"}
    res = {"common_period": score(common, min_n), "five_members_full_period": score(full5, min_n)}
    n_common = len(next(iter(common.values()), []))
    print(f"Hindcast: Open-Meteo Historical Forecast (short-lead runs) vs SQV and WC3 snow-water gain, cold wet 12Z-12Z windows")
    for name, stats in (("All six members, " + COMMON_FROM + " on (" + str(n_common) + " site-days)", res["common_period"]),
                        ("Five members (no AIFS), WY2023 on", res["five_members_full_period"])):
        print(f"\n{name}\n  model            n   bias (in)  MAE (in)  weight")
        for m, s in sorted(stats.items(), key=lambda kv: kv[1]["mae"]):
            print(f"  {m:14} {s['n']:4}   {s['bias']:+8.3f}  {s['mae']:8.3f}  {s['weight'] if s['weight'] is not None else '-'}")
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        out = HINDCAST_DIR.parent / "blend_weights_hindcast.json"
        out.write_text(json.dumps({"created": datetime.now(timezone.utc).isoformat(), "min_n": min_n, "sites": list(HINDCAST_SITES),
                                   "common_from": COMMON_FROM, "common_site_days": n_common, "results": res}, indent=1, default=str))
        print(f"\nSaved {out} (config/sources.json is unchanged)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-n", type=int, default=15, help="wet windows a model needs per lead day")
    ap.add_argument("--write", action="store_true", help="save the suggestion to data/tuning/blend_weights.json")
    ap.add_argument("--hindcast", action="store_true", help="fit from Open-Meteo's archived forecasts instead of the live archive")
    a = ap.parse_args()
    if a.hindcast:
        return run_hindcast(a.min_n, a.write)
    snaps = daily_snapshots()
    rows = load_snotel()
    if not snaps:
        print(f"No archived model forecasts yet in {ARCHIVE}. Every pipeline run adds one (python3 server.py).")
        return 1
    if not rows:
        print("No SNOTEL data. Run: python3 nrcs_sync.py")
        return 1
    res = suggest(pairs(snaps, rows), a.min_n)
    print(f"{len(snaps)} daily snapshots; Palisades mid tier vs SQV snow-water gain, cold wet 24 h windows")
    for lead, stats in res.items():
        print(f"\n{lead}: model            n   bias (in)  MAE (in)  suggested weight")
        for m, s in sorted(stats.items(), key=lambda kv: kv[1]["mae"]):
            print(f"        {m:14} {s['n']:3}   {s['bias']:+8.3f}  {s['mae']:8.3f}  {s['weight'] if s['weight'] is not None else f'(needs {a.min_n} windows)'}")
        if not stats:
            print("        no cold wet windows yet")
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"created": datetime.now(timezone.utc).isoformat(), "min_n": a.min_n, "leads": res}, indent=1))
        print(f"\nSaved {OUT} (config/sources.json is unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
