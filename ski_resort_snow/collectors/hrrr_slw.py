"""Supercooled liquid water above the resort summits, from the native GRIB2 output of NOAA's
3 km convection-allowing models on AWS: HRRR (to 48 h) and RRFS (to 84 h).

NBM and Open-Meteo carry no cloud liquid water, so this reads the models' pressure-level files
directly (no authentication), each with a text index (.idx) of every message's byte offset:
  HRRR  https://noaa-hrrr-bdp-pds.s3.amazonaws.com
        hrrr.YYYYMMDD/conus/hrrr.tHHz.wrfprsfFF.grib2 (about 430 MB each)
  RRFS  https://noaa-rrfs-ops-pds.s3.amazonaws.com
        rrfs.YYYYMMDD/HH/rrfs.tHHz.prslev.3km.fFFF.conus.grib2 (about 570 MB each); the terrain
        height is in the 2-D file, rrfs.tHHz.2dfld.3km.fFFF.conus.grib2
Both run the Thompson-Eidhammer aerosol-aware microphysics (HRRR in WRF, RRFS in FV3), which
carries cloud water, rain, snow, graupel and cloud ice as separate mixing ratios. RRFS's CONUS
output is on HRRR's 3 km Lambert grid with the same packing, so the same cells and code serve
both; cloud ice is CIMIXR (1/82) in HRRR and ICMR (1/23) in RRFS.

Run used: the latest complete 00/06/12/18Z cycle (the runs that reach 48 h in HRRR and 84 h in
RRFS; complete = its last hour's index is on AWS), from the current hour to its end.

Per forecast hour only these messages are downloaded, by HTTP range:
  TMP at 775-450 hPa every 25 hPa, read only as far as the summit cells
      (nbm_archive.ArchiveReader.fetch_message: sections 1-6, the group tables and the data
      up to the cells, about 70% of each message)
  cloud water, cloud ice, rain, snow, graupel at the same levels, adjacent in the file: one
      request per level
  HGT at 700 hPa (partial): anchors the heights of the other levels
  HGT at the surface (partial, first hours of a cycle only): the cells' model terrain
HRRR: about 11.8 MB per hour and 0.55 GB per cycle (Nov 24, 2026: 47 hours in 70 s). RRFS's
messages are larger: about 15 MB per hour and 1.2 GB per cycle. Downloaded once and cached in
data/cache/ ({model}_slw_YYYYMMDDHH.json, last 4 cycles per model kept). Each message's GRIB2
codes are checked before use, and only the summit cells are decoded (grib2_complex.values_at).
Hours run in a pool of worker processes, each downloading one hour over kept-alive connections;
if a pool cannot start, the hours run in threads here.

Derived per hour at each summit's nearest grid cell (3 km, the same cell in both models):
  level heights   hypsometric from HGT at 700 hPa and the TMP profile (dry air, < 0.3% error)
  surface         pressure at the cell's model terrain; levels below it are left out
  supercooled liquid   cloud water + rain water at levels colder than 0 °C
  column          its integral from the model surface to 450 hPa, kg/m² (= mm of water)
  riming layer    supercooled liquid >= 0.01 g/kg with snow + graupel >= 0.01 g/kg
  summit          temperature and supercooled liquid at the summit's height
"""

import http.client
import json
import math
import multiprocessing
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from . import http_ssl
    from .grib2_complex import sections, storage_index, values_at
    from .grib2_simple import parse_grid, parse_product
    from .nbm_archive import ArchiveReader, _request, cell_latlon, grid_ij, grid_key, parse_idx
except ImportError:
    import http_ssl
    from grib2_complex import sections, storage_index, values_at
    from grib2_simple import parse_grid, parse_product
    from nbm_archive import ArchiveReader, _request, cell_latlon, grid_ij, grid_key, parse_idx

USER_AGENT = "SierraSnowDashboard/3.0 (HRRR/RRFS supercooled liquid)"
LEVELS_HPA = list(range(775, 449, -25))     # 775 ... 450; the summit cells' terrain is near 765-775 hPa
ANCHOR_HPA = 700
# Per model: file paths ("prs" pressure levels; "sfc" the file with the terrain height when it is not
# in "prs"), the last forecast hour of the 00/06/12/18Z runs, and the hydrometeor short names.
MODELS: Dict[str, Dict[str, Any]] = {
    "hrrr": {"name": "HRRR", "bucket": "https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
             "prs": "hrrr.{c:%Y%m%d}/conus/hrrr.t{c:%H}z.wrfprsf{fh:02d}.grib2", "sfc": None, "last_fh": 48,
             "hydro": ("CLMR", "CIMIXR", "RWMR", "SNMR", "GRLE"),
             "source": "NOAA HRRR on AWS (noaa-hrrr-bdp-pds), wrfprs pressure-level GRIB2, native fields"},
    "rrfs": {"name": "RRFS", "bucket": "https://noaa-rrfs-ops-pds.s3.amazonaws.com",
             "prs": "rrfs.{c:%Y%m%d}/{c:%H}/rrfs.t{c:%H}z.prslev.3km.f{fh:03d}.conus.grib2",
             "sfc": "rrfs.{c:%Y%m%d}/{c:%H}/rrfs.t{c:%H}z.2dfld.3km.f{fh:03d}.conus.grib2", "last_fh": 84,
             "hydro": ("CLMR", "ICMR", "RWMR", "SNMR", "GRLE"),
             "source": "NOAA RRFS on AWS (noaa-rrfs-ops-pds), prslev 3 km CONUS GRIB2, native fields"},
}
SHORT = {"CLMR": "qc", "CIMIXR": "qi", "ICMR": "qi", "RWMR": "qr", "SNMR": "qs", "GRLE": "qg"}
CODES = {"TMP": (0, 0), "HGT": (3, 5), "CLMR": (1, 22), "CIMIXR": (1, 82), "ICMR": (1, 23), "RWMR": (1, 24),
         "SNMR": (1, 25), "GRLE": (1, 32)}      # (category, parameter), discipline 0 (meteorological)
LIQ_MIN = 0.01        # g/kg: supercooled liquid counted for a riming layer from here
SNOW_MIN = 0.01       # g/kg: snow + graupel in the same layer
CACHE_VERSION = 1
KEEP_CYCLES = 4       # per model
DEADLINE_S = 420      # stop waiting for hours after this; finished hours stay cached
RD, G0 = 287.05, 9.80665
M_TO_FT = 3.28084


def _idx_fields(hydro):
    tail = r":(?:(\d+) hour fcst|anl):$"
    out = [(re.compile(rf"^{n}:{p} mb{tail}"), f"{n}:{p}") for n in ("TMP",) + tuple(hydro) for p in LEVELS_HPA]
    out.append((re.compile(rf"^HGT:{ANCHOR_HPA} mb{tail}"), f"HGT:{ANCHOR_HPA}"))
    out.append((re.compile(rf"^HGT:surface{tail}"), "HGT:surface"))
    return out


IDX_FIELDS = {m: _idx_fields(spec["hydro"]) for m, spec in MODELS.items()}


def file_url(cycle: datetime, fh: int, model: str = "hrrr", kind: str = "prs") -> str:
    spec = MODELS[model]
    return f"{spec['bucket']}/{spec[kind].format(c=cycle, fh=fh)}"


def iso_hour(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%MZ")      # same form as the Open-Meteo timelines


def latest_cycle(now: Optional[datetime] = None, model: str = "hrrr", lookback_h: int = 36) -> Optional[datetime]:
    """Newest 00/06/12/18Z cycle whose last-hour index is on AWS (one 1-byte request per cycle tried)."""
    now = now or datetime.now(timezone.utc)
    c = now.replace(minute=0, second=0, microsecond=0)
    c -= timedelta(hours=c.hour % 6)
    while now - c <= timedelta(hours=lookback_h):
        try:
            _request(file_url(c, MODELS[model]["last_fh"], model) + ".idx", (0, 0), tries=2, timeout=20)
            return c
        except urllib.error.HTTPError as e:
            e.close()
            if e.code not in (403, 404):
                raise
        c -= timedelta(hours=6)
    return None


# ---------------------------------------------------------------- one forecast hour (worker)
_LOCAL = threading.local()
_CTX: Optional[ssl.SSLContext] = None


def _get(url: str, rng: Optional[Tuple[int, Optional[int]]] = None, tries: int = 4, timeout: int = 60) -> bytes:
    """GET (a byte range of) url on this thread's kept-alive HTTPS connection.

    Same contract as nbm_archive._request (HTTPError at once for 403/404, retries otherwise),
    but an hour's ~30 range requests reuse a few connections: about half the time per request."""
    global _CTX
    if _CTX is None:
        _CTX = http_ssl._build_context() or ssl.create_default_context()   # same CA fix as urllib's opener
    u = urllib.parse.urlsplit(url)
    headers = {"User-Agent": USER_AGENT}
    if rng:
        headers["Range"] = f"bytes={rng[0]}-{'' if rng[1] is None else rng[1]}"
    conns = _LOCAL.__dict__.setdefault("conns", {})
    for attempt in range(tries):
        conn = conns.get(u.netloc)
        if conn is None:
            conn = conns[u.netloc] = http.client.HTTPSConnection(u.netloc, timeout=timeout, context=_CTX)
        try:
            conn.request("GET", u.path, headers=headers)
            r = conn.getresponse()
            if rng and r.status == 200:            # never read a whole 430 MB file by accident
                conn.close()
                raise ValueError(f"{url}: server ignored the byte range")
            data = r.read()
        except (http.client.HTTPException, OSError):
            conn.close()
            conns.pop(u.netloc, None)
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
            continue
        if r.status in (200, 206):
            return data
        if r.status in (403, 404) or attempt == tries - 1:
            raise urllib.error.HTTPError(url, r.status, r.reason, r.headers, None)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


class CellReader(ArchiveReader):
    """ArchiveReader whose box is a list of points, each at its nearest grid cell."""

    # The summit cells are ~60% of the way through the grid, so a message is needed to about 71%
    # of its bytes (the group tables come first): asking for 75% at once makes one request out of three.
    head_frac = 0.75

    def __init__(self, latlons: List[Tuple[float, float]]):
        super().__init__()
        self.latlons = [tuple(x) for x in latlons]

    def request(self, url, rng):
        return _get(url, rng)

    def layout(self, grid: Dict[str, Any]) -> Dict[str, Any]:
        k = grid_key(grid)
        if k not in self.layouts:
            ij = []
            for la, lo in self.latlons:
                fi, fj = grid_ij(grid, la, lo)
                i, j = int(round(fi)), int(round(fj))
                if not (0 <= i < grid["nx"] and 0 <= j < grid["ny"]):
                    raise ValueError(f"{la}, {lo} is outside the grid")
                ij.append((i, j))
            st = [storage_index(i, j, grid["nx"], grid["scan"]) for i, j in ij]
            self.layouts[k] = {"ij": ij, "storage": st, "stop": max(st) + 1, "grid": grid}
        return self.layouts[k]


def _blocks(want: Dict[str, Tuple[int, Optional[int]]], keys: List[str]):
    """Byte-adjacent messages merged into one range: [((first, last), [keys]), ...]."""
    out: List[Tuple[Tuple[int, Optional[int]], List[str]]] = []
    for (a, b), k in sorted((want[k], k) for k in keys):
        if out and out[-1][0][1] is not None and out[-1][0][1] + 1 == a:
            out[-1] = ((out[-1][0][0], b), out[-1][1] + [k])
        else:
            out.append(((a, b), [k]))
    return out


def _split(data: bytes) -> List[bytes]:
    """The GRIB2 messages of a byte range that starts at a message."""
    out, k = [], 0
    while k < len(data):
        if data[k:k + 4] != b"GRIB":
            raise ValueError("byte range does not start at a GRIB message")
        ln = int.from_bytes(data[k + 8:k + 16], "big")
        if ln < 16:
            raise ValueError(f"GRIB message length {ln} is not valid")
        out.append(data[k:k + ln])
        k += ln
    return out


def check_codes(msg: bytes, key: str, fh: int) -> Dict[str, Any]:
    """The message's sections, after checking it is the field, level and hour the index named."""
    sec = sections(msg)
    prod = parse_product(sec[4])
    name, lev = key.split(":")
    cat, par = CODES[name]
    if lev == "surface":
        level_ok = prod["lev_type"] == 1
    else:
        level_ok = prod["lev_type"] == 100 and prod["lev_val"] is not None and abs(prod["lev_val"] - int(lev) * 100) < 1
    if msg[6] != 0 or prod["pdt"] != 0 or (prod["cat"], prod["par"]) != (cat, par) or not level_ok \
            or prod["fct_unit"] != 1 or prod["fct"] != fh:
        raise ValueError(f"{key} hour {fh}: GRIB2 codes discipline {msg[6]}, {prod} do not match")
    return sec


def _cell_values(msg: bytes, key: str, fh: int, reader: CellReader) -> List[float]:
    sec = check_codes(msg, key, fh)
    grid = parse_grid(sec[3])
    if grid is None:
        raise ValueError(f"{key}: grid is not Lambert conformal (template 3.30)")
    lay = reader.layout(grid)
    v = values_at(sec[5], sec[7], lay["storage"])
    return [v[s] for s in lay["storage"]]


def fetch_hour(cycle: str, fh: int, latlons: List[Tuple[float, float]], terrain: bool = False,
               threads: int = 8, model: str = "hrrr") -> Dict[str, Any]:
    """Download and decode one forecast hour at the points' cells (runs in a worker process).

    cycle "YYYYMMDDHH", model a key of MODELS. Returns {"fh", "cells": [per point: {"t_c", "qc",
    "qi", "qr", "qs", "qg" (775-450 hPa, °C and g/kg), "z700_m", "terrain_m" (if asked)}], "ij",
    "bytes"} or {"fh", "error"}.
    """
    try:
        spec = MODELS[model]
        cyc = datetime.strptime(cycle, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        url = file_url(cyc, fh, model)
        try:
            idx = _get(url + ".idx").decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            e.close()
            return {"fh": fh, "error": f"index HTTP {e.code}"}
        want = parse_idx(idx, fh, IDX_FIELDS[model])
        partial = [f"TMP:{p}" for p in LEVELS_HPA] + [f"HGT:{ANCHOR_HPA}"]
        hydro = [f"{n}:{p}" for p in LEVELS_HPA for n in spec["hydro"]]
        total = len(idx)
        jobs: List[Tuple[str, Any, Tuple[int, Optional[int]], str]] = []
        if terrain and spec["sfc"]:          # terrain height in a second file (RRFS 2dfld)
            surl = file_url(cyc, fh, model, "sfc")
            try:
                sidx = _get(surl + ".idx").decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                e.close()
                return {"fh": fh, "error": f"2-D index HTTP {e.code}"}
            total += len(sidx)
            sfc = parse_idx(sidx, fh, IDX_FIELDS[model]).get("HGT:surface")
            if sfc is None:
                return {"fh": fh, "error": "2-D index has no HGT:surface"}
            jobs.append(("partial", "HGT:surface", sfc, surl))
        elif terrain:
            partial.append("HGT:surface")
        lacking = [k for k in partial + hydro if k not in want]
        if lacking:
            return {"fh": fh, "error": f"index has no {', '.join(lacking[:4])}{' ...' if len(lacking) > 4 else ''}"}
        reader = CellReader(latlons)
        jobs += [("partial", k, want[k], url) for k in partial] + [("block", keys, rng, url) for rng, keys in _blocks(want, hydro)]

        def run(job):
            kind, key, rng, u = job
            if kind == "partial":
                msg, _, nb = reader.fetch_message(u, rng)
                return [(key, msg)], nb
            data = _get(u, rng)
            msgs = _split(data)
            if len(msgs) != len(key):
                raise ValueError(f"bytes {rng}: {len(msgs)} messages where the index lists {len(key)}")
            return list(zip(key, msgs)), len(data)

        vals: Dict[str, List[float]] = {}
        pool = ThreadPoolExecutor(threads)
        try:
            for fut in as_completed([pool.submit(run, j) for j in jobs]):
                items, nb = fut.result()
                total += nb
                for key, msg in items:
                    vals[key] = _cell_values(msg, key, fh, reader)
        finally:                    # after a failure, skip the downloads not yet started
            pool.shutdown(wait=True, cancel_futures=True)
        lay = next(iter(reader.layouts.values()))
        cells = []
        for c in range(len(latlons)):
            cell: Dict[str, Any] = {"t_c": [round(vals[f"TMP:{p}"][c] - 273.15, 2) for p in LEVELS_HPA],
                                    "z700_m": round(vals[f"HGT:{ANCHOR_HPA}"][c], 1)}
            for n in spec["hydro"]:   # kg/kg -> g/kg; packing can leave values a hair below 0
                cell[SHORT[n]] = [round(max(0.0, vals[f"{n}:{p}"][c]) * 1000.0, 5) for p in LEVELS_HPA]
            if terrain:
                cell["terrain_m"] = round(vals["HGT:surface"][c], 1)
            cells.append(cell)
        g = lay["grid"]
        return {"fh": fh, "cells": cells, "ij": [list(x) for x in lay["ij"]], "bytes": total,
                "cell_latlon": [list(map(lambda v: round(v, 4), cell_latlon(g, i, j))) for i, j in lay["ij"]]}
    except Exception as e:      # reported per hour; the hour is retried on the next refresh
        return {"fh": fh, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- column diagnostics
def level_heights(levels: List[float], t_c: List[float], z_anchor: float, p_anchor: float = ANCHOR_HPA) -> List[float]:
    """Heights (m) of the pressure levels from one known height, hypsometric with the layer-mean
    temperature (dry air: leaving out moisture changes a 25 hPa layer's depth by under 0.3%)."""
    k0 = levels.index(p_anchor)
    z = [0.0] * len(levels)
    z[k0] = z_anchor
    for k in range(k0 + 1, len(levels)):
        z[k] = z[k - 1] + RD * ((t_c[k - 1] + t_c[k]) / 2 + 273.15) / G0 * math.log(levels[k - 1] / levels[k])
    for k in range(k0 - 1, -1, -1):
        z[k] = z[k + 1] - RD * ((t_c[k + 1] + t_c[k]) / 2 + 273.15) / G0 * math.log(levels[k] / levels[k + 1])
    return z


def surface_pressure(levels: List[float], z: List[float], t_c: List[float], z_sfc: float) -> float:
    """Pressure (hPa) at the model terrain height, hypsometric from the level just below or above."""
    k = 0
    while k + 1 < len(levels) - 1 and z[k + 1] < z_sfc:
        k += 1
    # layer k..k+1 holds z_sfc (or the lowest layer extended down when the terrain is below it)
    f = (z_sfc - z[k]) / (z[k + 1] - z[k])
    t_sfc = t_c[k] + f * (t_c[k + 1] - t_c[k])
    tm = (t_c[k] + t_sfc) / 2 + 273.15
    return levels[k] * math.exp(-(z_sfc - z[k]) * G0 / (RD * tm))


def layer_weights(levels: List[float], psfc: float) -> List[float]:
    """Pressure depth (hPa) each level stands for between the surface and the top level: from the
    midpoints to its neighbors; the lowest level above ground reaches down to the surface, the top
    level stops at itself, levels below ground get 0. The weights add up to psfc - top."""
    w = [0.0] * len(levels)
    above = [k for k, p in enumerate(levels) if p <= psfc]
    for n, k in enumerate(above):
        lo = psfc if n == 0 else (levels[k] + levels[k - 1]) / 2
        hi = (levels[k] + levels[k + 1]) / 2 if k + 1 < len(levels) else levels[k]
        w[k] = max(0.0, lo - hi)
    return w


def derive_hour(levels: List[float], cell: Dict[str, Any], terrain_m: float, summit_m: Optional[float]) -> Dict[str, Any]:
    """Supercooled liquid, riming layers and column totals for one hour at one cell."""
    t = cell["t_c"]
    z = level_heights(levels, t, cell["z700_m"])
    ps = surface_pressure(levels, z, t, terrain_m)
    w = layer_weights(levels, ps)
    qc, qr, qs, qg = cell["qc"], cell["qr"], cell["qs"], cell["qg"]
    n = len(levels)
    slw = [qc[k] + qr[k] if (w[k] > 0 and t[k] < 0) else 0.0 for k in range(n)]
    rime = [1 if slw[k] >= LIQ_MIN and qs[k] + qg[k] >= SNOW_MIN else 0 for k in range(n)]
    per_hpa = 1e-3 * 100.0 / G0                   # g/kg over 1 hPa -> kg/m²
    col = sum(slw[k] * w[k] for k in range(n)) * per_hpa
    rime_col = sum(slw[k] * w[k] for k in range(n) if rime[k]) * per_hpa
    gr_col = sum(qg[k] * w[k] for k in range(n) if t[k] < 0) * per_hpa
    out = {"psfc_hpa": round(ps, 1), "z_m": [round(v) for v in z], "t_c": [round(v, 1) for v in t],
           **{key: [round(v, 4) for v in cell[key]] for key in ("qc", "qr", "qs", "qg", "qi")},
           "slw": [round(v, 4) for v in slw], "rime": rime,
           "slw_col_kg_m2": round(col, 4), "rime_col_kg_m2": round(rime_col, 4), "graupel_col_kg_m2": round(gr_col, 4),
           "summit": None}
    if summit_m is not None:
        for k in range(n - 1):
            if z[k] <= summit_m <= z[k + 1] and w[k] > 0:
                f = (summit_m - z[k]) / (z[k + 1] - z[k])
                ts = t[k] + f * (t[k + 1] - t[k])
                liq = (1 - f) * (qc[k] + qr[k]) + f * (qc[k + 1] + qr[k + 1])
                out["summit"] = {"p_hpa": round(math.exp(math.log(levels[k]) + f * (math.log(levels[k + 1]) - math.log(levels[k]))), 1),
                                 "t_c": round(ts, 1), "slw_g_kg": round(liq if ts < 0 else 0.0, 4)}
                break
    return out


# ---------------------------------------------------------------- client
def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.replace(path)


class SLWClient:
    """One model's supercooled liquid at the summits (model: "hrrr" or "rrfs")."""

    def __init__(self, cache_dir: Path, model: str = "hrrr", workers: Optional[int] = None, deadline_s: float = DEADLINE_S):
        if model not in MODELS:
            raise ValueError(f"unknown model {model!r}; expected one of {', '.join(MODELS)}")
        self.model, self.spec = model, MODELS[model]
        self.cache_dir = Path(cache_dir)
        self.workers = workers if workers is not None else max(1, min(8, (os.cpu_count() or 2) - 1))
        self.deadline_s = deadline_s

    def _run(self, cycle: str, jobs: List[Tuple], on_result: Callable[[Dict[str, Any]], None],
             say: Callable[[str], None]) -> None:
        """fetch_hour for every job: worker processes if possible, else threads here."""
        pending = {j[1]: j for j in jobs}
        deadline = time.monotonic() + self.deadline_s
        name = self.spec["name"]

        def collect(futs):
            for f in as_completed(futs, timeout=max(1.0, deadline - time.monotonic())):
                r = f.result()
                pending.pop(r["fh"], None)
                on_result(r)

        if self.workers > 1 and len(jobs) > 1:
            pool = None
            try:
                pool = ProcessPoolExecutor(max_workers=min(self.workers, len(jobs)), mp_context=multiprocessing.get_context("spawn"))
                collect([pool.submit(fetch_hour, *j, model=self.model) for j in jobs])
            except FuturesTimeout:
                say(f"{name}: stopped after {self.deadline_s:.0f} s, {len(pending)} hours left for the next refresh")
                pending.clear()
            except Exception as e:          # no worker processes here: finish in threads
                say(f"{name}: worker processes unavailable ({type(e).__name__}), using threads")
            finally:
                if pool is not None:
                    pool.shutdown(wait=False, cancel_futures=True)
        if pending:
            tp = ThreadPoolExecutor(max_workers=3)
            try:
                collect([tp.submit(fetch_hour, *j, threads=4, model=self.model) for j in list(pending.values())])
            except FuturesTimeout:
                say(f"{name}: stopped after {self.deadline_s:.0f} s, {len(pending)} hours left for the next refresh")
            finally:
                tp.shutdown(wait=False, cancel_futures=True)

    def _prune(self) -> None:
        for old in sorted(self.cache_dir.glob(f"{self.model}_slw_*.json"))[:-KEEP_CYCLES]:
            try:
                old.unlink()
            except OSError:
                pass

    def fetch(self, points: Dict[str, Dict[str, float]], progress: Optional[Callable[[str], None]] = None,
              now: Optional[datetime] = None) -> Dict[str, Any]:
        """points: {id: {"lat", "lon", "elevation_ft"}} -> {"status", "cycle_utc", "points": {id: payload}}."""
        say = progress or (lambda m: None)
        now = now or datetime.now(timezone.utc)
        started = time.monotonic()
        name = self.spec["name"]
        cycle = latest_cycle(now, self.model)
        if cycle is None:
            return {"status": "error", "error_message": f"no complete 00/06/12/18Z {name} cycle on AWS in the last 36 h"}
        cyc = cycle.strftime("%Y%m%d%H")
        hour0 = now.replace(minute=0, second=0, microsecond=0)
        fhs = [fh for fh in range(self.spec["last_fh"] + 1) if cycle + timedelta(hours=fh) >= hour0]
        ids = list(points)
        latlons = [[round(points[i]["lat"], 4), round(points[i]["lon"], 4)] for i in ids]
        path = self.cache_dir / f"{self.model}_slw_{cyc}.json"
        cache = _load(path)
        if cache.get("cache_version") != CACHE_VERSION or cache.get("latlons") != latlons or cache.get("levels_hpa") != LEVELS_HPA:
            cache = {"cache_version": CACHE_VERSION, "cycle_utc": iso_hour(cycle), "source": self.spec["bucket"], "levels_hpa": LEVELS_HPA,
                     "latlons": latlons, "ij": None, "cell_latlon": None, "terrain_m": None, "hours": {}, "errors": {}, "bytes": 0}
        todo = [fh for fh in fhs if str(fh) not in cache["hours"]]
        new_bytes = 0
        if todo:
            say(f"{name} {cycle:%H}Z: {len(todo)} hours to download")
            need_terrain = cache.get("terrain_m") is None
            jobs = [(cyc, fh, [tuple(x) for x in latlons], need_terrain and k < 2) for k, fh in enumerate(todo)]
            done = [0]

            def on_result(r):
                nonlocal new_bytes
                fh = str(r["fh"])
                if r.get("error"):
                    cache["errors"][fh] = r["error"]
                else:
                    cache["errors"].pop(fh, None)
                    cells = r["cells"]
                    if cells and "terrain_m" in cells[0] and cache.get("terrain_m") is None:
                        cache["terrain_m"] = [c.pop("terrain_m") for c in cells]
                    for c in cells:
                        c.pop("terrain_m", None)
                    cache["hours"][fh] = cells
                    cache["ij"], cache["cell_latlon"] = r["ij"], r["cell_latlon"]
                    new_bytes += r.get("bytes", 0)
                    cache["bytes"] = cache.get("bytes", 0) + r.get("bytes", 0)
                done[0] += 1
                if done[0] % 8 == 0 or done[0] == len(todo):
                    say(f"{name} {cycle:%H}Z: {done[0]}/{len(todo)} hours")
                cache["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
                _save(path, cache)

            self._run(cyc, jobs, on_result, say)
            self._prune()
        have = [fh for fh in fhs if str(fh) in cache["hours"]]
        if not have or cache.get("terrain_m") is None:
            errs = sorted(set(cache.get("errors", {}).values()))
            what = "no hours decoded" if not have else "model terrain not read yet (retried on the next refresh)"
            return {"status": "error", "cycle_utc": iso_hour(cycle),
                    "error_message": f"{name} {cycle:%HZ %b %d}: {what}" + (f" ({errs[0]})" if errs else "")}
        out = {}
        for c, pid in enumerate(ids):
            pt = points[pid]
            summit_m = pt["elevation_ft"] / M_TO_FT if pt.get("elevation_ft") else None
            terrain = cache["terrain_m"][c]
            hours = []
            for fh in have:
                d = derive_hour(LEVELS_HPA, cache["hours"][str(fh)][c], terrain, summit_m)
                hours.append({"time": iso_hour(cycle + timedelta(hours=fh)), "fh": fh, **d})
            i, j = cache["ij"][c]
            la, lo = cache["cell_latlon"][c]
            out[pid] = {
                "status": "success", "model": name, "cycle_utc": iso_hour(cycle), "last_fh": self.spec["last_fh"],
                "source": self.spec["source"],
                "fh_range": [have[0], have[-1]], "missing_hours": [fh for fh in fhs if fh not in have],
                "levels_hpa": LEVELS_HPA, "column_top_hpa": LEVELS_HPA[-1],
                "thresholds_g_kg": {"liquid": LIQ_MIN, "snow_graupel": SNOW_MIN},
                "cell": {"i": i, "j": j, "lat": la, "lon": lo, "terrain_ft": round(terrain * M_TO_FT),
                         "offset_km": round(math.hypot((lo - pt["lon"]) * 111.32 * math.cos(math.radians(pt["lat"])), (la - pt["lat"]) * 110.57), 1)},
                "point": {"lat": pt["lat"], "lon": pt["lon"], "elevation_ft": pt.get("elevation_ft")},
                "download": {"hours_downloaded": len(todo) - sum(1 for fh in todo if str(fh) not in cache["hours"]),
                             "mb_this_run": round(new_bytes / 1e6, 1), "mb_cycle": round(cache.get("bytes", 0) / 1e6, 1),
                             "seconds": round(time.monotonic() - started, 1), "from_cache": not todo},
                "hours": hours,
            }
        return {"status": "success", "cycle_utc": iso_hour(cycle), "points": out}


if __name__ == "__main__":       # python3 collectors/hrrr_slw.py [--model rrfs]: fetch for the summits, print the columns
    import argparse
    ap = argparse.ArgumentParser(description="Supercooled liquid at the resort summits from HRRR or RRFS (cached in data/cache/)")
    ap.add_argument("--model", choices=sorted(MODELS), default="hrrr")
    args = ap.parse_args()
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config" / "resorts.json").read_text())
    pts = {r["id"]: {"lat": r["elevations"]["summit"]["latitude"], "lon": r["elevations"]["summit"]["longitude"],
                     "elevation_ft": r["elevations"]["summit"]["feet"]} for r in cfg["resorts"]}
    res = SLWClient(Path(__file__).resolve().parent.parent / "data" / "cache", args.model).fetch(pts, progress=lambda m: print(m, file=sys.stderr))
    if res["status"] != "success":
        sys.exit(res.get("error_message"))
    for pid, p in res["points"].items():
        print(f"{pid}: {p['model']} {p['cycle_utc']} hours {p['fh_range']}, cell {p['cell']}, {p['download']}")
        for h in p["hours"]:
            s = h["summit"] or {}
            print(f"  {h['time']}  column {h['slw_col_kg_m2']:.3f} kg/m2  riming {h['rime_col_kg_m2']:.3f}  "
                  f"graupel {h['graupel_col_kg_m2']:.3f}  summit {s.get('t_c')} C {s.get('slw_g_kg')} g/kg  psfc {h['psfc_hpa']}")
