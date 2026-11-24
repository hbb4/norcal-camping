"""GRIB2 complex packing (data templates 5.2 and 5.3), standard library only.

The full NBM CONUS files on AWS (one 2345 x 1597 grid, 3.7 million points per field) use
data template 5.3: complex packing with spatial differencing, no bitmap, and scanning mode
0x50 (rows south to north, adjacent rows in opposite directions). NOMADS's grib filter
repacks its subsets as simple packing, which grib2_simple.py reads; this module reads the
archive files.

Complex packing stores the field as groups. Each group has a reference value, a bit width
and a length; its values are reference + an unsigned integer of that width. With spatial
differencing (5.3) the unpacked numbers are first or second differences along the storage
order, so the field has to be integrated from its first point. decode() therefore always
starts at point 0, but can stop after `stop` points, which for a box in the Sierra is a
little over half the grid.

Order 2 differencing, f(n) = d(n) + 2 f(n-1) - f(n-2), is computed as two running sums
(g = f(n) - f(n-1) accumulates d, f accumulates g) with itertools.accumulate.

Missing value management 1 and 2 (primary / secondary missing values) is supported:
missing points are skipped by the differencing and returned as None.
"""

import struct
from itertools import accumulate
from typing import Any, Dict, List, Optional

CHUNK = 256   # values per big-integer slice when unpacking (keeps shifts cheap)


def _sm(v: int, nbits: int) -> int:
    """Sign-magnitude integer of nbits."""
    sign = 1 << (nbits - 1)
    return -(v & (sign - 1)) if v & sign else v


def _uints(buf: bytes, bitpos: int, width: int, count: int) -> List[int]:
    """`count` unsigned integers of `width` bits starting at bit `bitpos` (MSB first)."""
    if width == 0 or count == 0:
        return [0] * count
    mask = (1 << width) - 1
    out: List[int] = []
    for c0 in range(0, count, CHUNK):
        n = min(CHUNK, count - c0)
        start = bitpos + c0 * width
        b0, skip = start >> 3, start & 7
        nb = skip + n * width
        b1 = b0 + ((nb + 7) >> 3)
        big = int.from_bytes(buf[b0:b1], "big") >> ((b1 - b0) * 8 - nb)
        out.extend((big >> (width * (n - 1 - k))) & mask for k in range(n))
    return out


def drs_params(sec5: bytes) -> Dict[str, Any]:
    """Section 5 for templates 5.2 / 5.3."""
    tmpl = struct.unpack(">H", sec5[9:11])[0]
    if tmpl not in (2, 3):
        raise ValueError(f"data template 5.{tmpl} is not complex packing")
    s = sec5
    p = {"tmpl": tmpl, "npts": struct.unpack(">I", s[5:9])[0],
         "R": struct.unpack(">f", s[11:15])[0],
         "E": _sm(struct.unpack(">H", s[15:17])[0], 16), "D": _sm(struct.unpack(">H", s[17:19])[0], 16),
         "nbits": s[19], "orig_type": s[20], "split": s[21], "missing": s[22],
         "ng": struct.unpack(">I", s[31:35])[0], "ref_width": s[35], "bits_width": s[36],
         "ref_len": struct.unpack(">I", s[37:41])[0], "len_incr": s[41],
         "last_len": struct.unpack(">I", s[42:46])[0], "bits_len": s[46]}
    if tmpl == 3:
        p["order"], p["extra_octets"] = s[47], s[48]
    return p


def decode(sec5: bytes, sec7: bytes, stop: Optional[int] = None) -> List[Optional[float]]:
    """Values of the first `stop` points (all points if None) in storage order."""
    p = drs_params(sec5)
    npts = p["npts"]
    stop = npts if stop is None else min(stop, npts)
    buf = sec7[5:]
    pos = 0                                   # bit position in buf
    ival1 = ival2 = minsd = 0
    order = p.get("order", 0)
    if p["tmpl"] == 3 and order in (1, 2):
        nb = p["extra_octets"] * 8
        ival1 = _sm(_uints(buf, pos, nb, 1)[0], nb); pos += nb
        if order == 2:
            ival2 = _sm(_uints(buf, pos, nb, 1)[0], nb); pos += nb
        minsd = _sm(_uints(buf, pos, nb, 1)[0], nb); pos += nb
    ng = p["ng"]

    def block(width, count):
        nonlocal pos
        vals = _uints(buf, pos, width, count)
        pos += width * count
        pos = (pos + 7) & ~7                  # each block starts on a byte boundary
        return vals

    refs = block(p["nbits"], ng)
    widths = [w + p["ref_width"] for w in block(p["bits_width"], ng)]
    lens = [p["ref_len"] + v * p["len_incr"] for v in block(p["bits_len"], ng)]
    if ng:
        lens[-1] = p["last_len"]

    miss1 = p["missing"] in (1, 2)
    miss2 = p["missing"] == 2
    gmiss1 = (1 << p["nbits"]) - 1 if p["nbits"] else None
    gmiss2 = gmiss1 - 1 if gmiss1 else None
    seq: List[int] = []                       # packed integers of non-missing points
    missing_at: List[int] = []                # storage indices of missing points (rare)
    done = 0
    for ref, w, ln in zip(refs, widths, lens):
        if done >= stop:
            break
        take = min(ln, stop - done)
        if w == 0:
            if miss1 and gmiss1 is not None and (ref == gmiss1 or (miss2 and ref == gmiss2)):
                missing_at.extend(range(done, done + take))
            else:
                seq.extend([ref] * take)
        else:
            xs = _uints(buf, pos, w, take)
            if miss1:
                m1 = (1 << w) - 1
                m2 = m1 - 1 if miss2 else None
                for k, x in enumerate(xs):
                    if x == m1 or x == m2:
                        missing_at.append(done + k)
                    else:
                        seq.append(ref + x)
            else:
                seq.extend([ref + x for x in xs])
        pos += w * ln
        done += take

    if p["tmpl"] == 3 and seq:
        if order == 1:
            seq = list(accumulate([ival1] + [x + minsd for x in seq[1:]]))
        elif order == 2:
            if len(seq) == 1:
                seq = [ival1]
            else:
                g = accumulate([ival2 - ival1] + [x + minsd for x in seq[2:]])
                seq = list(accumulate([ival1] + list(g)))

    bscale, dscale, R = 2.0 ** p["E"], 10.0 ** -p["D"], p["R"]
    vals = [(R + x * bscale) * dscale for x in seq]
    if not missing_at:
        return vals
    out: List[Optional[float]] = [None] * (len(vals) + len(missing_at))
    miss = set(missing_at)
    it = iter(vals)
    for i in range(len(out)):
        if i not in miss:
            out[i] = next(it)
    return out


def storage_index(i: int, j: int, nx: int, scan: int) -> int:
    """Storage position of grid column i, row j (both counted in the file's scan directions).

    Bit 0x10 of the scanning mode: adjacent rows scan in opposite directions, so odd rows are
    stored right to left. Bit 0x20 (columns consecutive) is not used by NBM and not supported.
    """
    if scan & 0x20:
        raise ValueError("scanning mode with consecutive columns is not supported")
    if scan & 0x10 and j % 2 == 1:
        return j * nx + (nx - 1 - i)
    return j * nx + i


def sections(msg: bytes) -> Dict[int, bytes]:
    """First occurrence of each section (1-7) of one GRIB2 message."""
    if msg[:4] != b"GRIB" or msg[7] != 2:
        raise ValueError("not a GRIB2 message")
    out: Dict[int, bytes] = {}
    k = 16
    while k < len(msg) - 4 and msg[k:k + 4] != b"7777":
        ln = struct.unpack(">I", msg[k:k + 4])[0]
        out.setdefault(msg[k + 4], msg[k:k + ln])
        k += ln
    return out
