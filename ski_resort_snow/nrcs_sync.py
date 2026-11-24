#!/usr/bin/env python3
"""Download NRCS SNOTEL hourly data (snow water, depth, precipitation, air temperature) for calibration.

    python3 nrcs_sync.py                  update: merge values added or edited since the last sync
                                          (runs the backfill first if nothing is downloaded yet)
    python3 nrcs_sync.py backfill         download missing water years from WY2021 (and the current one)
    python3 nrcs_sync.py backfill --from-wy 2018 --refresh
                                          start earlier / download every water year again
    python3 nrcs_sync.py status           what is on disk

Seven SNOTEL sites around Palisades and Alpine (TUNING_PLAN.md section 2). Output goes to
data/tuning/nrcs/<CDEC code>/WY<yyyy>.csv (not committed). AWDB keeps the full hourly record, so this
doesn't need a schedule; run an update before building a calibration sample.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from collectors import http_ssl  # noqa: E402
from collectors import nrcs_client as nrcs  # noqa: E402

OUT = BASE_DIR / "data" / "tuning" / "nrcs"


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def do_status():
    r = nrcs.status(OUT)
    st = r["state"]
    print(f"Synced to {st.get('last_sync_pst', 'never')} PST, from WY{st.get('first_wy', '-')}; folder {OUT}")
    for s in r["sites"]:
        if not s["water_years"]:
            print(f"  {s['code']}: nothing downloaded")
            continue
        h = s.get("latest_hours_with", {})
        print(f"  {s['code']}: {s['water_years'][0]}–{s['water_years'][-1]} ({len(s['water_years'])} files); "
              f"latest file {s['latest_file_hours']} h: " + ", ".join(f"{k} {v}" for k, v in h.items())
              + f"; last snow water {s.get('last_wteq_pst')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="update", choices=["update", "backfill", "status"])
    ap.add_argument("--from-wy", type=int, default=nrcs.FIRST_WY, help="first water year for backfill")
    ap.add_argument("--refresh", action="store_true", help="backfill: download every water year again")
    a = ap.parse_args()
    http_ssl.install()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.command == "status":
        return do_status()
    if a.command == "backfill":
        print(f"{stamp()} backfill from WY{a.from_wy}{' (refresh)' if a.refresh else ''}")
        r = nrcs.backfill(OUT, first_wy=a.from_wy, refresh=a.refresh)
        print(f"{stamp()} backfill: {r['requests']} requests, synced to {r['synced_to']} PST")
        return 0
    r = nrcs.update(OUT, log=lambda m: print(m))
    if "backfill" in r:
        print(f"{stamp()} nothing downloaded yet; backfill: {r['backfill']['requests']} requests, "
              f"synced to {r['backfill']['synced_to']} PST")
    else:
        ch = ", ".join(f"{k} {v} h" for k, v in r["changed"].items()) or "no changes"
        print(f"{stamp()} update: values added or edited since {r['since_pst']} PST: {ch}; synced to {r['synced_to']} PST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
