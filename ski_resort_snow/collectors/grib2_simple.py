"""Minimal GRIB2 reader for NOAA NBM subsets (standard library only).

Supports what NOMADS's grib filter returns for NBM: Lambert conformal grids
(grid template 3.30), simple packing (data template 5.0) with an optional
bitmap, and product templates 4.0 (instantaneous), 4.8 (accumulation),
4.9 (probability over an interval). Anything else is skipped.
"""

import math
import struct
from typing import Any, Dict, Iterator, List, Optional, Tuple


def _sm16(b: bytes) -> int:
    """GRIB2 sign-magnitude 16-bit integer."""
    v = struct.unpack(">H", b)[0]
    return -(v & 0x7FFF) if v & 0x8000 else v


def _sm32(b: bytes) -> int:
    v = struct.unpack(">I", b)[0]
    return -(v & 0x7FFFFFFF) if v & 0x80000000 else v


def _unpack_bits(data: bytes, nbits: int, count: int) -> List[int]:
    if nbits == 0:
        return [0] * count
    out, acc, accbits, mask, i = [], 0, 0, (1 << nbits) - 1, 0
    for byte in data:
        acc = (acc << 8) | byte
        accbits += 8
        while accbits >= nbits and i < count:
            accbits -= nbits
            out.append((acc >> accbits) & mask)
            i += 1
        acc &= (1 << accbits) - 1 if accbits else 0
        if i >= count:
            break
    return out


def _lambert_latlon(g: Dict[str, Any]) -> List[Tuple[float, float]]:
    """Lat/lon of every grid point for template 3.30 (spherical earth)."""
    R = g["radius"]
    lat1, lat2, latd = map(math.radians, (g["latin1"], g["latin2"], g["lad"]))
    lov = math.radians(g["lov"])
    if abs(lat1 - lat2) < 1e-9:
        n = math.sin(lat1)
    else:
        n = math.log(math.cos(lat1) / math.cos(lat2)) / math.log(math.tan(math.pi / 4 + lat2 / 2) / math.tan(math.pi / 4 + lat1 / 2))
    F = math.cos(lat1) * math.tan(math.pi / 4 + lat1 / 2) ** n / n

    def fwd(lat, lon):
        rho = R * F / math.tan(math.pi / 4 + lat / 2) ** n
        th = n * (lon - lov)
        return rho * math.sin(th), -rho * math.cos(th)

    x0, y0 = fwd(math.radians(g["la1"]), math.radians(g["lo1"]))
    pts = []
    rho_sign = 1 if n > 0 else -1
    for j in range(g["ny"]):
        for i in range(g["nx"]):
            x = x0 + i * g["dx"] * (1 if not g["scan"] & 0x80 else -1)
            y = y0 + j * g["dy"] * (1 if g["scan"] & 0x40 else -1)
            rho = rho_sign * math.hypot(x, y)
            th = math.atan2(x, -y) if n > 0 else math.atan2(-x, y)
            lat = 2 * math.atan((R * F / rho) ** (1 / n)) - math.pi / 2
            lon = lov + th / n
            pts.append((math.degrees(lat), (math.degrees(lon) + 540) % 360 - 180))
    return pts


def read_messages(buf: bytes) -> Iterator[Dict[str, Any]]:
    pos = 0
    while True:
        j = buf.find(b"GRIB", pos)
        if j < 0:
            return
        disc = buf[j + 6]
        total = struct.unpack(">Q", buf[j + 8:j + 16])[0]
        msg = buf[j:j + total]
        pos = j + total
        k = 16
        grid = prod = drs = None
        bitmap = None
        values = None
        while k < len(msg) - 4:
            if msg[k:k + 4] == b"7777":
                break
            ln = struct.unpack(">I", msg[k:k + 4])[0]
            sec = msg[k + 4]
            s = msg[k:k + ln]
            if sec == 3:
                tmpl = struct.unpack(">H", s[12:14])[0]
                if tmpl == 30:
                    shape = s[14]
                    radius = 6371229.0 if shape == 6 else (struct.unpack(">I", s[16:20])[0] * 10 ** -s[15] if shape == 1 else 6371229.0)
                    grid = {"tmpl": 30, "radius": radius,
                            "nx": struct.unpack(">I", s[30:34])[0], "ny": struct.unpack(">I", s[34:38])[0],
                            "la1": _sm32(s[38:42]) * 1e-6, "lo1": struct.unpack(">I", s[42:46])[0] * 1e-6,
                            "lad": _sm32(s[47:51]) * 1e-6, "lov": struct.unpack(">I", s[51:55])[0] * 1e-6,
                            "dx": struct.unpack(">I", s[55:59])[0] * 1e-3, "dy": struct.unpack(">I", s[59:63])[0] * 1e-3,
                            "scan": s[64], "latin1": _sm32(s[65:69]) * 1e-6, "latin2": _sm32(s[69:73]) * 1e-6}
                    grid["lo1"] = (grid["lo1"] + 180) % 360 - 180
                    grid["lov"] = (grid["lov"] + 180) % 360 - 180
            elif sec == 4:
                pdt = struct.unpack(">H", s[7:9])[0]
                p = {"pdt": pdt, "cat": s[9], "par": s[10], "fct": struct.unpack(">I", s[18:22])[0], "fct_unit": s[17],
                     "lev_type": s[22], "lev_val": _sm32(s[24:28]) * 10 ** -s[23] if s[23] != 255 else None}
                if pdt == 8:
                    p["acc_len"] = struct.unpack(">I", s[49:53])[0]
                elif pdt == 9:
                    p["prob_type"] = s[36]
                    p["prob_lower"] = _sm32(s[38:42]) * 10 ** -s[37]
                    p["acc_len"] = struct.unpack(">I", s[62:66])[0]
                prod = p
            elif sec == 5:
                tmpl = struct.unpack(">H", s[9:11])[0]
                npts = struct.unpack(">I", s[5:9])[0]
                if tmpl == 0:
                    drs = {"n": npts, "R": struct.unpack(">f", s[11:15])[0], "E": _sm16(s[15:17]), "D": _sm16(s[17:19]), "nbits": s[19]}
            elif sec == 6:
                if s[5] == 0:
                    bitmap = _unpack_bits(s[6:], 1, 10 ** 9)
            elif sec == 7 and drs:
                raw = _unpack_bits(s[5:], drs["nbits"], drs["n"])
                scale_e, scale_d = 2.0 ** drs["E"], 10.0 ** drs["D"]
                vals = [(drs["R"] + x * scale_e) / scale_d for x in raw]
                if bitmap is not None:
                    it = iter(vals)
                    values = [next(it) if bit else None for bit in bitmap[: (grid["nx"] * grid["ny"] if grid else len(bitmap))]]
                else:
                    values = vals
            k += ln
        if grid and prod and values is not None:
            yield {"disc": disc, **prod, "grid": grid, "values": values}


def nearest_index(grid: Dict[str, Any], lat: float, lon: float, cache: Dict[Tuple, Any]) -> Tuple[int, float, float]:
    key = tuple(sorted((k, v) for k, v in grid.items() if k != "tmpl"))
    if key not in cache:
        cache[key] = _lambert_latlon(grid)
    pts = cache[key]
    kx = math.cos(math.radians(lat))
    best = min(range(len(pts)), key=lambda i: (pts[i][0] - lat) ** 2 + ((pts[i][1] - lon) * kx) ** 2)
    return best, pts[best][0], pts[best][1]
