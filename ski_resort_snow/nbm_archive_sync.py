#!/usr/bin/env python3
"""Past NBM forecasts for SNOTEL storm-days (TUNING_PLAN.md step 3).

    python3 nbm_archive_sync.py storm-days        find storm-days in the SNOTEL hourly data
                                                  (run nrcs_sync.py first) -> data/tuning/storm_days.json
    python3 nbm_archive_sync.py fetch             download NBM day-1 forecasts for every confirmed storm-day
        --leads 1,2,3                             also day 2 and day 3 (cycles 24 h / 48 h earlier)
        --from 2024-10-01 --to 2025-09-30         limit the dates
        --limit 10                                stop after this many cycles (for a trial run)
        --all-days                                include storm-days not confirmed by a gauge or other sites
    python3 nbm_archive_sync.py terrain           terrain height of every extended-box cell (api.weather.gov, once)
    python3 nbm_archive_sync.py status            what is on disk

Each NBM cycle is one file, data/tuning/nbm/cycles/nbm_YYYYMMDDHH.json, holding the 6 h
precipitation and snowfall, 2 m temperature and dew point, snow/liquid ratio and snow level
for a 22 x 31 box of 2.5 km cells around the seven SNOTEL sites, at forecast hours ending at
12Z, 18Z, 00Z and 06Z of the storm-day. A download resumes where it stopped. About 4 MB and
4 seconds per forecast hour; one lead for all confirmed storm-days is roughly 6 GB.
"""

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from collectors import http_ssl  # noqa: E402
from collectors import nbm_archive as na  # noqa: E402
from collectors import storm_days as sdm  # noqa: E402
from collectors.grid_terrain import terrain_ft  # noqa: E402
from collectors.nrcs_client import SITES  # noqa: E402

TUNING = BASE_DIR / "data" / "tuning"
OUT = TUNING / "nbm"
STORM_DAYS = TUNING / "storm_days.json"
NRCS = TUNING / "nrcs"
LIVE_TERRAIN = BASE_DIR / "config" / "grid_terrain.json"
EXT_TERRAIN = OUT / "terrain.json"


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def live_latlons():
    keys = json.loads(LIVE_TERRAIN.read_text()) if LIVE_TERRAIN.exists() else {}
    return [tuple(map(float, k.split(","))) for k in keys]


def do_storm_days():
    if not any(NRCS.glob("*/WY*.csv")):
        print("No SNOTEL data yet. Run: python3 nrcs_sync.py")
        return 1
    days = sdm.storm_days(NRCS, report_sites=[c for _, c in SITES])
    TUNING.mkdir(parents=True, exist_ok=True)
    STORM_DAYS.write_text(json.dumps({
        "created": stamp(), "definition": f"12Z-12Z snow-water gain >= {sdm.THRESHOLD_IN} in at {' or '.join(sdm.DEFAULT_SITES)}",
        "confirmed_rule": f"trigger-site gauge >= {sdm.CONFIRM_GAUGE_IN} in, or >= 2 other sites gained >= {sdm.CONFIRM_SWE_IN} in",
        "days": days}, indent=1))
    conf = [d for d in days if d["confirmed"]]
    by_wy = {}
    for d in conf:
        y, m = int(d["date"][:4]), int(d["date"][5:7])
        by_wy[y + (1 if m >= 10 else 0)] = by_wy.get(y + (1 if m >= 10 else 0), 0) + 1
    print(f"{len(days)} storm-days, {len(conf)} confirmed -> {STORM_DAYS}")
    print("  confirmed by water year: " + ", ".join(f"WY{k} {v}" for k, v in sorted(by_wy.items())))
    return 0


def do_fetch(leads, d0, d1, limit, all_days):
    if not STORM_DAYS.exists():
        print("No storm-days yet. Run: python3 nbm_archive_sync.py storm-days")
        return 1
    days = json.loads(STORM_DAYS.read_text())["days"]
    days = [d for d in days if (all_days or d["confirmed"]) and (not d0 or d["date"] >= d0) and (not d1 or d["date"] <= d1)]
    first_archive = "2020-09-30"
    plan = {}
    for d in days:
        for lead in leads:
            cyc, hrs = na.lead_files(d["date"], lead)
            if cyc.strftime("%Y-%m-%d") < first_archive:
                continue
            plan.setdefault(cyc, set()).update(hrs)
    todo = sorted(plan.items())
    if limit:
        todo = todo[:limit]
    reader = na.ArchiveReader(live_latlons=live_latlons())
    print(f"{stamp()} fetch: {len(days)} storm-days, leads {','.join(map(str, leads))} -> {len(todo)} cycles, "
          f"{sum(len(h) for _, h in todo)} forecast hours (hours already on disk are skipped)")
    t0, total_bytes, new_hours, errors = time.time(), 0, 0, 0
    for n, (cyc, hrs) in enumerate(todo, 1):
        try:
            r = na.fetch_cycle_hours(reader, OUT, cyc, sorted(hrs))
        except Exception as e:  # keep going; a rerun retries this cycle
            errors += 1
            print(f"{stamp()}   {cyc:%Y-%m-%d %HZ}: failed: {type(e).__name__}: {e}")
            continue
        total_bytes += r["bytes"]
        new_hours += len(r["new_hours"])
        miss = {h: f for h, f in r["missing"].items() if int(h) in hrs}
        if r["new_hours"] or n % 25 == 0 or miss:
            el = time.time() - t0
            eta = el / n * (len(todo) - n)
            print(f"{stamp()}   {n}/{len(todo)} {cyc:%Y-%m-%d %HZ} v{na.nbm_version(cyc)}: +{len(r['new_hours'])} h"
                  f"{'; missing ' + json.dumps(miss) if miss else ''}; {total_bytes / 1e6:.0f} MB so far, ~{eta / 60:.0f} min left")
    print(f"{stamp()} fetch done: {new_hours} new forecast hours, {total_bytes / 1e9:.2f} GB, {errors} cycles failed"
          f"{' (rerun to retry)' if errors else ''}")
    return 1 if errors else 0


def do_terrain():
    files = sorted((OUT / "cycles").glob("nbm_*.json"))
    if not files:
        print("No NBM cycles yet. Run: python3 nbm_archive_sync.py fetch --limit 1")
        return 1
    box = json.loads(files[-1].read_text())["box"]
    if not EXT_TERRAIN.exists() and LIVE_TERRAIN.exists():   # start from the live box's cells
        OUT.mkdir(parents=True, exist_ok=True)
        EXT_TERRAIN.write_text(LIVE_TERRAIN.read_text())
    res = terrain_ft([tuple(p) for p in box["latlon"]], EXT_TERRAIN, progress=lambda m: print(f"{stamp()} {m}"))
    have = sum(1 for v in res.values() if v and v.get("elevation_ft") is not None)
    print(f"{stamp()} terrain: {have}/{len(res)} cells -> {EXT_TERRAIN}")
    return 0 if have == len(res) else 1


def do_status():
    files = sorted((OUT / "cycles").glob("nbm_*.json"))
    hours = 0
    versions = {}
    for f in files:
        d = json.loads(f.read_text())
        hours += len(d["rows"])
        versions[d["nbm_version"]] = versions.get(d["nbm_version"], 0) + 1
    size = sum(f.stat().st_size for f in files)
    sd = json.loads(STORM_DAYS.read_text())["days"] if STORM_DAYS.exists() else []
    print(f"storm-days: {len(sd)} ({sum(1 for d in sd if d['confirmed'])} confirmed)")
    print(f"NBM cycles: {len(files)}, {hours} forecast hours, {size / 1e6:.1f} MB on disk; by version: "
          + ", ".join(f"v{k} {v}" for k, v in sorted(versions.items())))
    if files:
        print(f"  first {files[0].stem[4:]}, last {files[-1].stem[4:]}")
    t = json.loads(EXT_TERRAIN.read_text()) if EXT_TERRAIN.exists() else {}
    print(f"terrain: {len(t)} cells in {EXT_TERRAIN.name if t else 'none yet'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["storm-days", "fetch", "terrain", "status"])
    ap.add_argument("--leads", default="1", help="forecast days, e.g. 1,2,3")
    ap.add_argument("--from", dest="d0", help="first storm-day (YYYY-MM-DD)")
    ap.add_argument("--to", dest="d1", help="last storm-day (YYYY-MM-DD)")
    ap.add_argument("--limit", type=int, help="stop after this many cycles")
    ap.add_argument("--all-days", action="store_true", help="include unconfirmed storm-days")
    a = ap.parse_args()
    http_ssl.install()
    if a.command == "storm-days":
        return do_storm_days()
    if a.command == "fetch":
        leads = sorted({int(x) for x in a.leads.split(",") if x.strip()})
        if not leads or min(leads) < 1 or max(leads) > 10:
            ap.error("--leads must be days 1-10")
        for v in (a.d0, a.d1):
            if v:
                date.fromisoformat(v)
        return do_fetch(leads, a.d0, a.d1, a.limit, a.all_days)
    if a.command == "terrain":
        return do_terrain()
    return do_status()


if __name__ == "__main__":
    sys.exit(main())
