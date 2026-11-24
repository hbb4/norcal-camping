#!/usr/bin/env python3
"""Keep the Central Sierra Snow Lab (CSSL) calibration data current.

    python3 cssl_sync.py            season log + Dryad version check (what cron runs)
    python3 cssl_sync.py season     only log the current season from cssl.berkeley.edu
    python3 cssl_sync.py check      only compare the Dryad archive version with the imported one
    python3 cssl_sync.py import [ZIP]
                                    unpack a Dryad zip downloaded in the browser
                                    (default: newest ~/Downloads/doi_10_6078_D1941T__v*.zip)
    python3 cssl_sync.py daily      rebuild archive/daily.csv from the imported files (no zip needed)

Output goes to data/tuning/cssl/ (not committed).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from collectors import http_ssl  # noqa: E402
from collectors import cssl_client as cssl  # noqa: E402

OUT = BASE_DIR / "data" / "tuning" / "cssl"
ARCHIVE = OUT / "archive"


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def do_season():
    r = cssl.sync_season(OUT)
    b = r["board"]
    print(f"{stamp()} season: {r['days']} days to {r['last_day']}, season snowfall {r['season_snow_in']} in; "
          f"board {b.get('board_updated_pst')} 24 h {b.get('snow_24h_in')} in, SWE {b.get('snow_24h_swe_in')} in"
          f"{' (logged)' if r['board_added'] else ' (already logged)'}")


def do_check():
    r = cssl.check_archive(ARCHIVE)
    msg = {"current": "archive is current",
           "not_imported": "archive not imported yet",
           "new_version": "a newer archive is on Dryad"}[r["state"]]
    print(f"{stamp()} dryad: {msg} (remote v{r['remote'].get('version_number')} published {r['remote'].get('publication_date')}, "
          f"local {r['local'] or 'none'})")
    if r["state"] != "current":
        print(f"    download in a browser: open '{r['page']}'  then 'Download full dataset' ({r['expected_zip']})")
        print(f"    then: python3 {Path(__file__).name} import")
    return r


def do_import(path):
    z = Path(path).expanduser() if path else cssl.find_zip()
    if not z or not z.exists():
        print(f"No Dryad zip found{f' at {z}' if z else ' in ~/Downloads'}. Open {cssl.DRYAD_PAGE} and use 'Download full dataset'.")
        return 1
    r = cssl.import_zip(z, ARCHIVE)
    print(f"Imported {r['files']} files ({r['csv']} CSV) into {r['folder']}")
    for header, files in r["header_variants"].items():
        print(f"  {len(files)} files with columns: {header}")
    for f, n in r["unnamed"].items():
        print(f"  {f}: {n} unnamed column(s) dropped")
    print_daily(r["daily"])
    return 0


def print_daily(d):
    print(f"Daily table: {d['file']}")
    print(f"  {d['days']} days, {d['water_years']} water years, {d['first']} to {d['last']}"
          f"; missing water years: {', '.join(map(str, d['missing_water_years'])) or 'none'}"
          f"; duplicate dates: {d['duplicate_dates']}")
    if d["unknown_columns"]:
        print(f"  columns not recognized (dropped): {', '.join(d['unknown_columns'])}")
    for field, vals in d["unparsed_values"].items():
        print(f"  {field}: non-numeric values left empty: {', '.join(vals)}")


def do_daily():
    v = ARCHIVE / "VERSION.json"
    if not v.exists():
        print(f"Nothing imported yet. Run: python3 {Path(__file__).name} import")
        return 1
    folder = ARCHIVE / json.loads(v.read_text())["folder"]
    print_daily(cssl.build_daily(folder, ARCHIVE / "daily.csv"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="all", choices=["all", "season", "check", "import", "daily"])
    ap.add_argument("zip", nargs="?", help="Dryad zip for 'import'")
    a = ap.parse_args()
    http_ssl.install()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.command == "import":
        return do_import(a.zip)
    if a.command == "daily":
        return do_daily()
    status = 0
    if a.command in ("all", "season"):
        try:
            do_season()
        except Exception as e:  # keep going to the archive check
            print(f"{stamp()} season: failed: {type(e).__name__}: {e}")
            status = 1
    if a.command in ("all", "check"):
        try:
            do_check()
        except Exception as e:
            print(f"{stamp()} dryad: check failed: {type(e).__name__}: {e}")
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
