"""Past NBM forecasts from the NOAA archive on AWS, for calibration and hindcasts.

Bucket: https://noaa-nbm-grib2-pds.s3.amazonaws.com (no authentication), core CONUS files
blend.YYYYMMDD/HH/core/blend.tHHz.core.fFFF.co.grib2 (120-200 MB each) with a text index
(.idx) giving each message's byte offset. Only the needed messages are downloaded, with HTTP
range requests (about 1 MB each), and decoded by grib2_complex.py.

The values are kept for a box of grid cells around all seven SNOTEL sites (EXT_BOX), stored
in the same layout the live pipeline uses for its NOMADS box (south to north rows, west to
east within a row), so nbm_downscale.Downscaler can be run on past cycles unchanged.
`live_cells` lists the extended-box cells that make up the live 72-cell box (the cells in
config/grid_terrain.json), so the live adjustment can be reproduced exactly.

Product checks reuse NBMClient._field, so a message is accepted only when its GRIB2 codes
match what the live client reads (e.g. snow/liquid ratio is local parameter 1/233, which the
index names SNOWLR from late 2022 and only by number before).
"""

import json
import math
import re
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .grib2_complex import decode, drs_params, sections, storage_index, _uints
    from .grib2_simple import parse_grid, parse_product
    from .nbm_client import NBMClient
except ImportError:
    from grib2_complex import decode, drs_params, sections, storage_index, _uints
    from grib2_simple import parse_grid, parse_product
    from nbm_client import NBMClient

BUCKET = "https://noaa-nbm-grib2-pds.s3.amazonaws.com"
USER_AGENT = "SierraSnowDashboard/3.0 (NBM archive)"
EXT_BOX = {"toplat": 39.50, "bottomlat": 38.92, "leftlon": -120.48, "rightlon": -120.04}   # 7 SNOTEL sites + ~8 km
VERSIONS = [("4.0", "2020-09-29"), ("4.1", "2023-01-17"), ("4.2", "2024-05-15"), ("4.3", "2025-05-27"),
            ("5.0", "2026-05-05")]

# idx text -> field name; checked again against the GRIB2 codes after download
IDX_FIELDS = [
    (re.compile(r"^APCP:surface:(\d+)-(\d+) hour acc fcst:$"), "apcp_{n}h"),
    (re.compile(r"^ASNOW:surface:(\d+)-(\d+) hour acc fcst:$"), "asnow_{n}h"),
    (re.compile(r"^TMP:2 m above ground:(\d+) hour fcst:$"), "tmp_k"),
    (re.compile(r"^DPT:2 m above ground:(\d+) hour fcst:$"), "dpt_k"),
    (re.compile(r"^(?:SNOWLR|var discipline=0 center=7 local_table=1 parmcat=1 parm=233):surface:(\d+) hour fcst:$"), "slr"),
    (re.compile(r"^SNOWLVL:0 m above mean sea level:(\d+) hour fcst:$"), "snowlvl_m"),
]
DEFAULT_FIELDS = ("apcp_6h", "asnow_6h", "tmp_k", "dpt_k", "slr", "snowlvl_m")
HEAD_MIN = 65536   # first request of a message: at least this many bytes, or a quarter of the message


def nbm_version(cycle: datetime) -> str:
    d = cycle.strftime("%Y-%m-%d")
    v = None
    for name, first in VERSIONS:
        if d >= first:
            v = name
    return v or "pre-4.0"


def file_url(cycle: datetime, fh: int) -> str:
    d, h = cycle.strftime("%Y%m%d"), cycle.strftime("%H")
    return f"{BUCKET}/blend.{d}/{h}/core/blend.t{h}z.core.f{fh:03d}.co.grib2"


def _request(url: str, rng: Optional[Tuple[int, Optional[int]]] = None, tries: int = 4, timeout: int = 60) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if rng:
        headers["Range"] = f"bytes={rng[0]}-{'' if rng[1] is None else rng[1]}"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, OSError):
            if attempt == tries - 1:
                raise
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def parse_idx(text: str, fh: int) -> Dict[str, Tuple[int, Optional[int]]]:
    """{field: (first byte, last byte or None)} for the wanted messages of one file."""
    lines = [ln.split(":", 3) for ln in text.strip().splitlines() if ln.count(":") >= 3]
    offs = [int(p[1]) for p in lines]
    out: Dict[str, Tuple[int, Optional[int]]] = {}
    for k, p in enumerate(lines):
        rest = p[3]
        for rx, name in IDX_FIELDS:
            m = rx.match(rest)
            if not m:
                continue
            g = m.groups()
            if len(g) == 2:                      # accumulation a-b ending at this file's hour
                a, b = int(g[0]), int(g[1])
                if b != fh:
                    continue
                key = name.format(n=b - a)
            else:
                if int(g[0]) != fh:
                    continue
                key = name
            end = offs[k + 1] - 1 if k + 1 < len(offs) else None
            out.setdefault(key, (offs[k], end))
    return out


# ---------------------------------------------------------------- grid geometry
def _lambert(grid: Dict[str, Any]):
    R = grid["radius"]
    lat1, lat2 = math.radians(grid["latin1"]), math.radians(grid["latin2"])
    lov = math.radians(grid["lov"])
    if abs(lat1 - lat2) < 1e-9:
        n = math.sin(lat1)
    else:
        n = math.log(math.cos(lat1) / math.cos(lat2)) / math.log(
            math.tan(math.pi / 4 + lat2 / 2) / math.tan(math.pi / 4 + lat1 / 2))
    F = math.cos(lat1) * math.tan(math.pi / 4 + lat1 / 2) ** n / n

    def fwd(lat, lon):
        rho = R * F / math.tan(math.pi / 4 + math.radians(lat) / 2) ** n
        th = n * (math.radians(lon) - lov)
        return rho * math.sin(th), -rho * math.cos(th)

    def inv(x, y):
        rho = (1 if n > 0 else -1) * math.hypot(x, y)
        th = math.atan2(x, -y) if n > 0 else math.atan2(-x, y)
        lat = 2 * math.atan((R * F / rho) ** (1 / n)) - math.pi / 2
        return math.degrees(lat), (math.degrees(lov + th / n) + 540) % 360 - 180

    return fwd, inv


def grid_ij(grid: Dict[str, Any], lat: float, lon: float) -> Tuple[float, float]:
    """Fractional column/row of a lat/lon in the file's scan directions."""
    fwd, _ = _lambert(grid)
    x0, y0 = fwd(grid["la1"], grid["lo1"])
    x, y = fwd(lat, lon)
    i = (x - x0) / grid["dx"] * (-1 if grid["scan"] & 0x80 else 1)
    j = (y - y0) / grid["dy"] * (1 if grid["scan"] & 0x40 else -1)
    return i, j


def cell_latlon(grid: Dict[str, Any], i: int, j: int) -> Tuple[float, float]:
    fwd, inv = _lambert(grid)
    x0, y0 = fwd(grid["la1"], grid["lo1"])
    x = x0 + i * grid["dx"] * (-1 if grid["scan"] & 0x80 else 1)
    y = y0 + j * grid["dy"] * (1 if grid["scan"] & 0x40 else -1)
    return inv(x, y)


def box_layout(grid: Dict[str, Any], box: Dict[str, float] = EXT_BOX,
               live_latlons: Optional[List[Tuple[float, float]]] = None) -> Dict[str, Any]:
    """ij rectangle covering the lat/lon box; cells listed south to north, west to east."""
    if not grid["scan"] & 0x40 or grid["scan"] & 0x80:
        raise ValueError("expected rows south to north, columns west to east")
    corners = [grid_ij(grid, la, lo) for la in (box["bottomlat"], box["toplat"]) for lo in (box["leftlon"], box["rightlon"])]
    i0, i1 = math.floor(min(c[0] for c in corners)), math.ceil(max(c[0] for c in corners))
    j0, j1 = math.floor(min(c[1] for c in corners)), math.ceil(max(c[1] for c in corners))
    cells, latlon = [], []
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            cells.append(storage_index(i, j, grid["nx"], grid["scan"]))
            la, lo = cell_latlon(grid, i, j)
            latlon.append([round(la, 4), round(lo, 4)])
    live = []
    if live_latlons:
        pos = {(round(a, 4), round(b, 4)): k for k, (a, b) in enumerate(latlon)}
        for la, lo in live_latlons:
            k = pos.get((round(la, 4), round(lo, 4)))
            if k is None:   # tolerate last-digit rounding differences
                k = min(range(len(latlon)), key=lambda q: (latlon[q][0] - la) ** 2 + (latlon[q][1] - lo) ** 2)
                if abs(latlon[k][0] - la) > 2e-4 or abs(latlon[k][1] - lo) > 2e-4:
                    raise ValueError(f"live box cell {la},{lo} is not on the archive grid")
            live.append(k)
            latlon[k] = [la, lo]       # same keys as config/grid_terrain.json
    return {"ij0": [i0, j0], "nx": i1 - i0 + 1, "ny": j1 - j0 + 1, "storage": cells, "latlon": latlon,
            "live_cells": live, "stop": max(cells) + 1}


def grid_key(grid: Dict[str, Any]) -> str:
    return json.dumps({k: grid[k] for k in sorted(grid)}, sort_keys=True)


# ---------------------------------------------------------------- one cycle
class ArchiveReader:
    def __init__(self, live_latlons: Optional[List[Tuple[float, float]]] = None, pause_s: float = 0.0):
        self.live_latlons = live_latlons
        self.layouts: Dict[str, Dict[str, Any]] = {}
        self.pause_s = pause_s

    def layout(self, grid: Dict[str, Any]) -> Dict[str, Any]:
        k = grid_key(grid)
        if k not in self.layouts:
            self.layouts[k] = box_layout(grid, EXT_BOX, self.live_latlons)
        return self.layouts[k]

    def fetch_message(self, url: str, rng: Tuple[int, Optional[int]]) -> Tuple[bytes, Dict[str, Any], int]:
        """Download one message only as far as the box needs (about two thirds of it).

        First request: the leading quarter of the message, which holds sections 1-6 and the
        group tables of section 7 (reference, width and length of every group). From those
        the byte where the box's last point ends is known; the second request fetches up to it.
        Returns (truncated message, layout, bytes downloaded).
        """
        a, b = rng
        if b is None:
            return (msg := _request(url, rng)), self.layout(parse_grid(sections(msg)[3])), len(msg)
        size = b - a + 1
        head = _request(url, (a, min(b, a + max(HEAD_MIN, size // 4) - 1)))
        while True:
            k, secs = 16, {}
            while k + 5 <= len(head) and head[k:k + 4] != b"7777":
                ln = int.from_bytes(head[k:k + 4], "big")
                secs[head[k + 4]] = (k, ln)
                if head[k + 4] == 7:
                    break
                k += ln
            if 7 in secs or len(head) >= size:
                break
            head += _request(url, (a + len(head), min(b, a + 2 * len(head) - 1)))
        s7_at, _ = secs[7]
        grid = parse_grid(head[secs[3][0]:secs[3][0] + secs[3][1]])
        layout = self.layout(grid)
        p = drs_params(head[secs[5][0]:secs[5][0] + secs[5][1]])
        nb = p.get("extra_octets", 0) * 8 * ({1: 2, 2: 3}.get(p.get("order", 0), 0))
        meta = [(p["nbits"], p["ng"]), (p["bits_width"], p["ng"]), (p["bits_len"], p["ng"])]
        meta_bits = nb
        for w, n in meta:
            meta_bits = ((meta_bits + w * n) + 7) & ~7
        meta_end = s7_at + 5 + meta_bits // 8
        if len(head) < meta_end:
            head += _request(url, (a + len(head), a + meta_end - 1))
        data = head[s7_at + 5:]
        pos = nb
        tables = []
        for w, n in meta:
            tables.append(_uints(data, pos, w, n))
            pos = ((pos + w * n) + 7) & ~7
        widths = [w + p["ref_width"] for w in tables[1]]
        lens = [p["ref_len"] + v * p["len_incr"] for v in tables[2]]
        if lens:
            lens[-1] = p["last_len"]
        bits, done = meta_bits, 0
        for w, ln in zip(widths, lens):
            if done >= layout["stop"]:
                break
            bits += w * ln
            done += ln
        need = min(size, s7_at + 5 + (bits + 7) // 8 + 8)
        if len(head) < need:
            head += _request(url, (a + len(head), a + need - 1))
        return head, layout, len(head)

    def _field_values(self, url: str, name: str, rng: Tuple[int, Optional[int]]):
        msg, layout, nbytes = self.fetch_message(url, rng)
        sec = sections(msg)
        m = {"disc": msg[6], **parse_product(sec[4])}
        if NBMClient._field(m) != name:
            raise ValueError(f"{url} {rng}: GRIB2 codes {m} are not {name}")
        vals = decode(sec[5], sec[7], stop=layout["stop"])
        return name, [None if vals[s] is None else round(vals[s], 4) for s in layout["storage"]], layout, nbytes

    def read_file(self, cycle: datetime, fh: int, fields=DEFAULT_FIELDS) -> Dict[str, Any]:
        """{"fields": {name: [box values]}, "missing": [...], "layout": ..., "bytes": n} for one forecast hour."""
        url = file_url(cycle, fh)
        try:
            idx = _request(url + ".idx").decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return {"fields": {}, "missing": list(fields), "error": f"index HTTP {e.code}", "bytes": 0}
        want = parse_idx(idx, fh)
        out: Dict[str, List[Optional[float]]] = {}
        missing = [n for n in fields if n not in want]
        layout, total = None, len(idx)
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, vals, layout, nbytes in pool.map(lambda n: self._field_values(url, n, want[n]),
                                                     [n for n in fields if n in want]):
                out[name] = vals
                total += nbytes
        if self.pause_s:
            time.sleep(self.pause_s)
        return {"fields": out, "missing": missing, "layout": layout, "bytes": total}


# ---------------------------------------------------------------- storm-day downloads
def lead_files(day: str, lead: int) -> Tuple[datetime, List[int]]:
    """Cycle and forecast hours whose 6 h accumulations cover storm-day `day` (12Z-12Z) at a lead in days."""
    d = datetime.fromisoformat(day).replace(hour=12, tzinfo=timezone.utc)
    cycle = d - timedelta(days=lead - 1)
    base = 24 * (lead - 1)
    return cycle, [base + 6, base + 12, base + 18, base + 24]


def cycle_path(out_dir: Path, cycle: datetime) -> Path:
    return Path(out_dir) / "cycles" / f"nbm_{cycle.strftime('%Y%m%d%H')}.json"


def load_cycle(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


def fetch_cycle_hours(reader: ArchiveReader, out_dir: Path, cycle: datetime, hours: List[int],
                      fields=DEFAULT_FIELDS) -> Dict[str, Any]:
    """Add the given forecast hours to the cycle's file (skipping hours already there)."""
    path = cycle_path(out_dir, cycle)
    data = load_cycle(path) or {"cycle_utc": cycle.strftime("%Y-%m-%dT%H:%MZ"), "nbm_version": nbm_version(cycle),
                                "source": BUCKET, "fields": list(fields), "box": None, "rows": {}, "missing": {}}
    got, nbytes = [], 0
    for fh in hours:
        if str(fh) in data["rows"] and set(fields) <= set(data["rows"][str(fh)]) | set(data["missing"].get(str(fh), [])):
            continue
        r = reader.read_file(cycle, fh, fields)
        nbytes += r.get("bytes", 0)
        if r.get("error") and not r["fields"]:
            data["missing"][str(fh)] = list(fields)
            data.setdefault("errors", {})[str(fh)] = r["error"]
            continue
        if data["box"] is None and r["layout"]:
            lay = r["layout"]
            data["box"] = {k: lay[k] for k in ("ij0", "nx", "ny", "latlon", "live_cells")}
        data["rows"][str(fh)] = r["fields"]
        if r["missing"]:
            data["missing"][str(fh)] = r["missing"]
        got.append(fh)
    if got or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")))
        tmp.replace(path)
    return {"cycle": data["cycle_utc"], "new_hours": got, "bytes": nbytes, "missing": data["missing"]}
