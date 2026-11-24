"""NRCS AWDB hourly SNOTEL data (snow water, depth, precipitation, air temperature) for calibration.

API: https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data (no authentication). Values are in
inches and °F, stamped in the station's time zone; all seven sites report dataTimeZone -8, i.e. fixed
PST with no daylight time. Suspect values are requested too (the API drops them by default) and every
value keeps its flags, so quality control is a decision of the sample builder, not the download:

    qc  V validated · E edited · S suspect · C bias-corrected (air temperature) · others as published
    qa  R raw · P provisional · A approved · blank when not reported

Storage: <out>/<CDEC code>/WY<yyyy>.csv, one row per hour of the water year (blank where AWDB has no
value), so gaps are explicit. backfill() downloads whole water years; update() merges only values that
AWDB inserted or changed since the last sync (insertOrUpdateBeginDate), which also picks up NRCS edits.

Python 3.9 compatible.
"""

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1"
USER_AGENT = "SierraSnowDashboard/3.0 (SNOTEL hourly)"
PST = timezone(timedelta(hours=-8))
FMT = "%Y-%m-%d %H:%M"
ELEMENTS = {"WTEQ": "wteq_in", "SNWD": "snwd_in", "PREC": "prec_in", "TOBS": "tobs_f"}
SITES = [  # (triplet, CDEC code), nearest to Palisades first; TUNING_PLAN.md section 2
    ("784:CA:SNTL", "SQV"), ("848:CA:SNTL", "WC3"), ("809:CA:SNTL", "TCC"), ("834:CA:SNTL", "TK2"),
    ("428:CA:SNTL", "CSL"), ("724:CA:SNTL", "RP2"), ("541:CA:SNTL", "IDP"),
]
FIRST_WY = 2021   # the NBM archive on AWS starts 2020-09-29, so hindcasts can't go earlier
FIELDS = ["time_pst", "time_utc"] + [c for col in ELEMENTS.values()
                                     for c in (col, col.split("_")[0] + "_qc", col.split("_")[0] + "_qa")]
STATE = "state.json"


def _get_json(url, tries=3, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, OSError):   # socket.timeout is not TimeoutError on 3.9
            if attempt == tries - 1:
                raise
        time.sleep(5 * (attempt + 1))


def water_year(t):
    return t.year + (1 if t.month >= 10 else 0)


def wy_bounds(wy):
    return datetime(wy - 1, 10, 1, 0, 0), datetime(wy, 9, 30, 23, 0)


def now_pst():
    return datetime.now(PST).replace(tzinfo=None, minute=0, second=0, microsecond=0)


def fetch(triplets, begin, end, changed_since=None):
    """Raw AWDB payload for hourly WTEQ/SNWD/PREC/TOBS between two PST datetimes."""
    q = {"stationTriplets": ",".join(triplets), "elements": ",".join(ELEMENTS), "duration": "HOURLY",
         "beginDate": begin.strftime(FMT), "endDate": end.strftime(FMT),
         "returnFlags": "true", "returnSuspectData": "true"}
    if changed_since is not None:
        q["insertOrUpdateBeginDate"] = changed_since.strftime(FMT)
    return _get_json(f"{API}/data?{urllib.parse.urlencode(q)}")


def station_metadata(triplets):
    q = {"stationTriplets": ",".join(triplets)}
    keep = ("stationTriplet", "name", "elevation", "latitude", "longitude", "dataTimeZone", "beginDate")
    return [{k: s.get(k) for k in keep} for s in _get_json(f"{API}/stations?{urllib.parse.urlencode(q)}")]


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def parse_values(payload):
    """{triplet: {time_pst: {column: value, <el>_qc: flag, <el>_qa: flag}}} from an AWDB payload."""
    out = {}
    for station in payload or []:
        rows = out.setdefault(station.get("stationTriplet"), {})
        for series in station.get("data") or []:
            col = ELEMENTS.get((series.get("stationElement") or {}).get("elementCode"))
            if not col:
                continue
            p = col.split("_")[0]
            for v in series.get("values") or []:
                t = v.get("date")
                if not t:
                    continue
                cell = rows.setdefault(t, {})
                cell[col] = _fmt(v.get("value"))
                cell[p + "_qc"] = v.get("qcFlag") or ""
                cell[p + "_qa"] = v.get("qaFlag") or ""
    return out


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {r["time_pst"]: r for r in csv.DictReader(f)}


def write_csv(path, rows, wy, until):
    """Write one water year, one row per hour from Oct 1 to min(Sep 30 23:00, until)."""
    start, end = wy_bounds(wy)
    end = min(end, until)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    n = filled = 0
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        t = start
        while t <= end:
            key = t.strftime(FMT)
            r = rows.get(key, {})
            w.writerow({**{k: r.get(k, "") for k in FIELDS}, "time_pst": key,
                        "time_utc": (t + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%MZ")})
            n += 1
            filled += any(r.get(c) not in (None, "") for c in ELEMENTS.values())
            t += timedelta(hours=1)
    tmp.replace(path)
    return {"hours": n, "hours_with_data": filled}


def apply_values(out_dir, parsed, until, wy_min=FIRST_WY, replace=False):
    """Merge parsed values into the per-site water-year files. Returns {code: {wy: changed hours}}."""
    codes = dict(SITES)
    changed = {}
    for triplet, rows in parsed.items():
        code = codes.get(triplet, triplet.replace(":", "_"))
        by_wy = {}
        for t, cell in rows.items():
            wy = water_year(datetime.strptime(t, FMT))
            if wy >= wy_min:
                by_wy.setdefault(wy, {})[t] = cell
        for wy, cells in sorted(by_wy.items()):
            path = Path(out_dir) / code / f"WY{wy}.csv"
            rows_now = {} if replace else read_csv(path)
            for t, cell in cells.items():
                rows_now.setdefault(t, {}).update(cell)
            write_csv(path, rows_now, wy, until)
            changed.setdefault(code, {})[wy] = len(cells)
    return changed


def _state(out_dir):
    p = Path(out_dir) / STATE
    return json.loads(p.read_text()) if p.exists() else {}


def _save_state(out_dir, state):
    (Path(out_dir) / STATE).write_text(json.dumps(state, indent=1))


def backfill(out_dir, first_wy=FIRST_WY, refresh=False, pause=1.0, log=print):
    """Download every water year from first_wy to now that isn't on disk (all of them with refresh)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = now_pst()
    meta = station_metadata([t for t, _ in SITES])
    (out_dir / "stations.json").write_text(json.dumps(
        {"source": f"{API}/stations", "fetched_pst": started.strftime(FMT), "sites": [
            {**m, "cdec": dict(SITES).get(m["stationTriplet"])} for m in meta]}, indent=1))
    tz = {m["stationTriplet"]: m.get("dataTimeZone") for m in meta}
    bad = [t for t, z in tz.items() if z != -8]
    if bad:
        raise RuntimeError(f"unexpected data time zone for {bad}; storage assumes fixed PST")
    fetched = 0
    for triplet, code in SITES:
        for wy in range(first_wy, water_year(started) + 1):
            path = out_dir / code / f"WY{wy}.csv"
            if path.exists() and not refresh and wy < water_year(started):
                continue
            begin, end = wy_bounds(wy)
            parsed = parse_values(fetch([triplet], begin, min(end, started)))
            stats = write_csv(path, parsed.get(triplet, {}), wy, started)
            log(f"  {code} WY{wy}: {stats['hours_with_data']}/{stats['hours']} hours with data")
            fetched += 1
            time.sleep(pause)
    st = _state(out_dir)
    st.update({"first_wy": min(first_wy, st.get("first_wy", first_wy)), "last_sync_pst": started.strftime(FMT)})
    _save_state(out_dir, st)
    return {"requests": fetched, "first_wy": st["first_wy"], "synced_to": st["last_sync_pst"]}


def update(out_dir, margin_hours=24, log=print):
    """Merge values AWDB inserted or changed since the last sync (minus a margin), for all sites at once."""
    out_dir = Path(out_dir)
    st = _state(out_dir)
    if not st.get("last_sync_pst"):
        return {"backfill": backfill(out_dir, log=log)}
    started = now_pst()
    since = datetime.strptime(st["last_sync_pst"], FMT) - timedelta(hours=margin_hours)
    begin, _ = wy_bounds(st.get("first_wy", FIRST_WY))
    parsed = parse_values(fetch([t for t, _ in SITES], begin, started, changed_since=since))
    changed = apply_values(out_dir, parsed, started, wy_min=st.get("first_wy", FIRST_WY))
    # the current water year's file always runs to the latest hour, even when nothing changed
    wy = water_year(started)
    for _, code in SITES:
        path = out_dir / code / f"WY{wy}.csv"
        if code not in changed or wy not in changed[code]:
            write_csv(path, read_csv(path), wy, started)
    st["last_sync_pst"] = started.strftime(FMT)
    _save_state(out_dir, st)
    return {"since_pst": since.strftime(FMT), "synced_to": st["last_sync_pst"],
            "changed": {c: sum(v.values()) for c, v in changed.items()}}


def status(out_dir):
    """Per site: water years on disk and, for the latest one, how many hours have each element."""
    out_dir = Path(out_dir)
    report = {"state": _state(out_dir), "sites": []}
    for _, code in SITES:
        files = sorted((out_dir / code).glob("WY*.csv"))
        entry = {"code": code, "water_years": [f.stem for f in files]}
        if files:
            rows = list(read_csv(files[-1]).values())
            entry["latest_file_hours"] = len(rows)
            entry["latest_hours_with"] = {col: sum(1 for r in rows if r.get(col)) for col in ELEMENTS.values()}
            last = next((r["time_pst"] for r in reversed(rows) if r.get("wteq_in")), None)
            entry["last_wteq_pst"] = last
        report["sites"].append(entry)
    return report
