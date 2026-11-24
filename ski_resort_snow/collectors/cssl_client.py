"""UC Berkeley Central Sierra Snow Lab (CSSL) data for snow/liquid-ratio calibration.

Two sources:

* cssl.berkeley.edu home page. It embeds the whole current water year as daily series
  (accumulated snowfall, accumulated precipitation, snowpack SWE) and shows the latest
  8 AM board reading (24 h snowfall and its water equivalent). The board's water
  equivalent is shown for the current day only, so it has to be logged as it appears.
* Dryad archive doi:10.6078/D1941T, one daily CSV per water year (WY1971 onward, no
  WY2020), republished after each water year. The metadata API is public; file downloads
  need either a browser (the page uses a bot check) or a Dryad API account, so the
  archive is imported from a zip the user downloaded.

Python 3.9 compatible (macOS cron uses /usr/bin/python3 unless PATH says otherwise).
"""

import csv
import io
import json
import re
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HOME_URL = "https://cssl.berkeley.edu/"
DRYAD_DOI = "doi:10.6078/D1941T"
DRYAD_PAGE = "https://datadryad.org/dataset/doi:10.6078/D1941T"
DRYAD_META = "https://datadryad.org/api/v2/datasets/doi%3A10.6078%2FD1941T"
ZIP_PREFIX = "doi_10_6078_D1941T"
USER_AGENT = "SierraSnowDashboard/3.0 (CSSL season log)"
PST = timezone(timedelta(hours=-8))

SERIES = {"snowfallData": "snow_accum_in", "precipitationData": "precip_accum_in", "sweData": "swe_in"}
CARDS = [  # visible label -> field; "24-Hour Snowfall" must not swallow "24-Hour Snowfall SWE"
    (r"24-Hour Snowfall SWE\s+([\d.]+)\s*in", "snow_24h_swe_in"),
    (r"24-Hour Snowfall\s+([\d.]+)\s*in", "snow_24h_in"),
    (r"48-Hour Snowfall\s+([\d.]+)\s*in", "snow_48h_in"),
    (r"7-Day Snowfall\s+([\d.]+)\s*in", "snow_7d_in"),
    (r"Current Temperature\s+(-?[\d.]+)\s*°F", "temp_f"),
    (r"Current Wind-Speed\s+([\d.]+)\s*mph", "wind_mph"),
]
BOARD_FIELDS = ["board_updated_pst", "fetched_at_utc", "snow_24h_in", "snow_24h_swe_in", "snow_48h_in",
                "snow_7d_in", "temp_f", "wind_mph"]

# Dryad CSV header -> field in the combined daily table. Matched by name, not position: WY2021 has an
# unnamed 13th column (a copy of New Snow) and most files start with a UTF-8 byte-order mark.
ARCHIVE_FIELDS = {
    "Date": "date",
    "Air Temp Max (C)": "tmax_c",
    "Air Temp Min (C)": "tmin_c",
    "24-hour Total Precip (mm)": "precip_mm",
    "Season Total Precip (mm)": "season_precip_mm",
    "% of Precip as Snow": "precip_snow_pct",      # given from WY1988 on; absent before
    "% of Precip as Rain": "precip_rain_pct",
    "New Snow (cm)": "new_snow_cm",                # boards at 08:00 + 16:00 PST, summed
    "Season Total Snow (cm)": "season_snow_cm",
    "Snowpack depth (cm)": "snow_depth_cm",
    "Snow Water Equivalent (cm)": "swe_cm",        # snowpack SWE; SNOTEL 428 at 00:00 from WY2021
    "Remarks": "remarks",
}
DAILY_FIELDS = ["date", "water_year", "tmax_c", "tmin_c", "precip_mm", "season_precip_mm", "precip_snow_pct",
                "precip_rain_pct", "precip_trace", "new_snow_cm", "new_snow_trace", "season_snow_cm", "snow_depth_cm", "swe_cm",
                "remarks", "source_file"]
MISSING = {"", "--", "NA", "N/A"}
TRACE = {"T", "TRACE"}
TRACE_FLAGS = {"new_snow_cm": "new_snow_trace", "precip_mm": "precip_trace"}


def _get(url, accept="text/html", timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _flight(html):
    """Concatenate the Next.js flight-data chunks that carry the page's props."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def _array_after(text, key):
    m = re.search(r'"%s"\s*:\s*\[' % re.escape(key), text)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for j in range(start, len(text)):
        ch = text[j]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:j + 1])
    return None


def _visible_text(html):
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", t)


def _board_time(text, today):
    """'Snowfall data last updated Nov 24, 8:11 AM PST' -> ISO time in PST."""
    m = re.search(r"last updated ([A-Z][a-z]{2}) (\d{1,2}), (\d{1,2}):(\d{2}) (AM|PM) PST", text)
    if not m:
        return None
    mon = datetime.strptime(m.group(1), "%b").month
    hour = int(m.group(3)) % 12 + (12 if m.group(5) == "PM" else 0)
    year = today.year - (1 if mon > today.month else 0)   # a December reading seen in January
    return datetime(year, mon, int(m.group(2)), hour, int(m.group(4)), tzinfo=PST).isoformat()


def parse_home(html, today=None):
    """Return {water_year, board{...}, daily[...]} from the CSSL home page HTML."""
    today = today or datetime.now(PST).date()
    flight = _flight(html)
    series = {}
    for key, field in SERIES.items():
        arr = _array_after(flight, key)
        if arr:
            series[field] = {int(d["dayIndex"]): d.get("current") for d in arr if "dayIndex" in d}
    snow = _array_after(flight, "snowfallData") or []
    first = next((d.get("date") for d in snow if re.match(r"\d{4}-\d{2}-\d{2}$", str(d.get("date", "")))), None)
    wy_start = date.fromisoformat(first) if first else date(today.year - (0 if today.month >= 10 else 1), 10, 1)
    days = sorted(set().union(*[set(v) for v in series.values()])) if series else []
    daily, prev = [], {"snow_accum_in": 0.0, "precip_accum_in": 0.0}   # accumulations start at zero on Oct 1
    for idx in days:
        d = wy_start + timedelta(days=idx - 1)
        if d > today:
            break
        row = {"date": d.isoformat()}
        for field, vals in series.items():
            v = vals.get(idx)
            row[field] = round(v, 3) if v is not None else None
        for field, new in (("snow_accum_in", "snow_new_in"), ("precip_accum_in", "precip_new_in")):
            cur, p = row.get(field), prev.get(field)
            row[new] = round(max(0.0, cur - p), 3) if cur is not None and p is not None else None
            if cur is not None:
                prev[field] = cur
        daily.append(row)

    text = _visible_text(html)
    board = {"board_updated_pst": _board_time(text, today)}
    for pattern, field in CARDS:
        m = re.search(pattern, text)
        board[field] = float(m.group(1)) if m else None
    return {"water_year": wy_start.year + 1, "wy_start": wy_start.isoformat(), "board": board, "daily": daily}


def sync_season(out_dir, html=None):
    """Fetch the home page, rewrite season_WY<yyyy>.json, append a new board reading to board_log.csv."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = html if html is not None else _get(HOME_URL)
    parsed = parse_home(html)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    season = {"source": HOME_URL, "fetched_at_utc": now, **parsed,
              "notes": "Accumulations in inches as published. snow_new_in / precip_new_in are day-to-day differences; "
                       "snowfall is read at 08:00 PST, precipitation at midnight, so pair them over storm totals."}
    path = out_dir / f"season_WY{parsed['water_year']}.json"
    path.write_text(json.dumps(season, indent=1))

    log = out_dir / "board_log.csv"
    board = {**parsed["board"], "fetched_at_utc": now}
    seen = set()
    if log.exists():
        with log.open() as f:
            seen = {r.get("board_updated_pst") for r in csv.DictReader(f)}
    added = False
    if board.get("board_updated_pst") and board["board_updated_pst"] not in seen:
        new = not log.exists()
        with log.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=BOARD_FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: board.get(k) for k in BOARD_FIELDS})
        added = True
    last = next((r for r in reversed(parsed["daily"]) if r.get("snow_accum_in") is not None), {})
    return {"season_file": str(path), "days": len(parsed["daily"]), "board_added": added, "board": parsed["board"],
            "season_snow_in": last.get("snow_accum_in"), "last_day": last.get("date")}


def dryad_metadata():
    d = json.loads(_get(DRYAD_META, accept="application/json"))
    return {"version_number": d.get("versionNumber"), "publication_date": d.get("publicationDate"),
            "last_modified": d.get("lastModificationDate"), "title": d.get("title")}


def check_archive(archive_dir):
    """Compare the public Dryad version with the imported one. No download."""
    archive_dir = Path(archive_dir)
    meta = dryad_metadata()
    local = {}
    vf = archive_dir / "VERSION.json"
    if vf.exists():
        local = json.loads(vf.read_text())
    pub = (meta.get("publication_date") or "").replace("-", "")
    if not local:
        state = "not_imported"
    elif local.get("zip_version") == pub:
        state = "current"
    else:
        state = "new_version"
    return {"state": state, "remote": meta, "local": local.get("zip_version"),
            "expected_zip": f"{ZIP_PREFIX}__v{pub}.zip" if pub else None, "page": DRYAD_PAGE}


def find_zip(downloads=None):
    folder = Path(downloads or Path.home() / "Downloads")
    zips = sorted(folder.glob(f"{ZIP_PREFIX}__v*.zip"))
    return zips[-1] if zips else None


def _read_csv(data):
    """Rows of a Dryad CSV with a clean header: no byte-order mark, no blank names, no unnamed trailing columns."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    if not rows:
        return [], [], 0
    raw = [h.replace("﻿", "").strip() for h in rows[0]]
    header = list(raw)
    while header and not header[-1]:
        header.pop()
    return header, rows[1:], len(raw) - len(header)


def import_zip(zip_path, archive_dir):
    """Unpack the Dryad zip (CSV/Markdown/text only, no paths), summarize each CSV's columns, build daily.csv."""
    zip_path, archive_dir = Path(zip_path), Path(archive_dir)
    m = re.search(r"__v(\d{8})\.zip$", zip_path.name)
    version = m.group(1) if m else "unknown"
    dest = archive_dir / f"v{version}"
    dest.mkdir(parents=True, exist_ok=True)
    columns, files = {}, []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            base = Path(name).name
            if info.is_dir() or not re.match(r"^[\w.\-]+\.(csv|md|txt)$", base):   # basename only: no paths
                continue
            if info.file_size > 5_000_000:
                continue
            data = z.read(info)
            (dest / base).write_bytes(data)
            files.append(base)
            if base.endswith(".csv"):
                header, body, unnamed = _read_csv(data)
                columns[base] = {"header": header, "rows": len(body), "unnamed_columns": unnamed,
                                 "byte_order_mark": data.startswith(b"\xef\xbb\xbf")}
    (dest / "columns.json").write_text(json.dumps(columns, indent=1))
    headers = {}
    for f, c in columns.items():
        headers.setdefault(" | ".join(c["header"]), []).append(f)
    (archive_dir / "VERSION.json").write_text(json.dumps(
        {"zip_version": version, "zip": zip_path.name, "imported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "folder": dest.name, "files": len(files)}, indent=1))
    daily = build_daily(dest, archive_dir / "daily.csv")
    return {"folder": str(dest), "files": len(files), "csv": len(columns), "header_variants": headers,
            "unnamed": {f: c["unnamed_columns"] for f, c in columns.items() if c["unnamed_columns"]}, "daily": daily}


def _value(v):
    v = (v or "").strip()
    if v in MISSING:
        return None
    if v.upper() in TRACE:
        return 0.0
    if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", v):   # "1,003" in season totals
        v = v.replace(",", "")
    try:
        return float(v)
    except ValueError:
        return v


def _fmt(v):
    return "" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def build_daily(folder, out_csv):
    """Combine the imported WY*.csv files into one table with plain field names (see ARCHIVE_FIELDS).

    Missing ("--", "NA", blank) becomes empty. A trace ("T") becomes 0; for new snow and 24 h precipitation
    it also sets new_snow_trace / precip_trace to 1. Thousands separators are removed. Columns are matched
    by header name; unknown or unnamed columns are dropped. Other non-numeric cells are left empty and listed.
    """
    folder, out_csv = Path(folder), Path(out_csv)
    out, unknown, unparsed, years = [], set(), {}, []
    for f in sorted(folder.glob("WY*.csv")):
        header, body, _ = _read_csv(f.read_bytes())
        idx = {}
        for i, h in enumerate(header):
            if h in ARCHIVE_FIELDS:
                idx[ARCHIVE_FIELDS[h]] = i
            else:
                unknown.add(h)
        if "date" not in idx:
            continue
        years.append(f.stem)
        for r in body:
            if not any(c.strip() for c in r):
                continue
            row = {"source_file": f.name}
            for field, i in idx.items():
                cell = r[i] if i < len(r) else ""
                if field in ("date", "remarks"):
                    v = cell.strip()
                    row[field] = "" if v in MISSING else v
                    continue
                if field in TRACE_FLAGS:
                    row[TRACE_FLAGS[field]] = 1 if cell.strip().upper() in TRACE else 0
                v = _value(cell)
                if isinstance(v, str):
                    unparsed.setdefault(field, set()).add(v)
                    v = None
                row[field] = v
            d = row.get("date", "")
            if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                row["water_year"] = int(d[:4]) + (1 if int(d[5:7]) >= 10 else 0)
            out.append(row)
    out.sort(key=lambda r: r.get("date", ""))
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DAILY_FIELDS)
        w.writeheader()
        for r in out:
            w.writerow({k: _fmt(r.get(k)) for k in DAILY_FIELDS})
    wys = sorted({r["water_year"] for r in out if "water_year" in r})
    gaps = [y for y in range(wys[0], wys[-1] + 1) if y not in wys] if wys else []
    dup = len(out) - len({r.get("date") for r in out})
    return {"file": str(out_csv), "days": len(out), "water_years": len(wys),
            "first": out[0].get("date") if out else None, "last": out[-1].get("date") if out else None,
            "missing_water_years": gaps, "duplicate_dates": dup, "unknown_columns": sorted(unknown),
            "unparsed_values": {k: sorted(v)[:10] for k, v in unparsed.items()}}
