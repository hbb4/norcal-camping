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

values_at() returns the value at a few points (HRRR summit cells) without building the
field: on HRRR files about 5x faster than decode() for temperature and 5-20x for cloud fields.
"""

import struct
import sys
from array import array
from itertools import accumulate
from operator import mul
from typing import Any, Dict, Iterable, List, Optional

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


# ---------------------------------------------------------------- values at a few points
_T01 = bytes.maketrans(b"01", b"\x00\x01")
_POP_W = 6 if hasattr(int, "bit_count") else 0   # widths up to this use bit-plane popcounts (Python 3.10+)
_POP_N = 256                                     # ... for runs of at most this many values
_MASKS: Dict[tuple, list] = {}


def _bits(buf: bytes, bitpos: int, nbits: int) -> int:
    """The nbits-bit unsigned integer at bit `bitpos` (MSB first)."""
    b0, b1 = bitpos >> 3, (bitpos + nbits + 7) >> 3
    if b1 > len(buf):
        raise ValueError("GRIB2 data section ends before the requested point (truncated download?)")
    return int.from_bytes(buf[b0:b1], "big") >> ((b1 << 3) - bitpos - nbits) & ((1 << nbits) - 1)


def _uints_fast(buf: bytes, bitpos: int, width: int, count: int) -> List[int]:
    """Same values as _uints, without a Python step per value (widths up to 16 bits).

    The bits are written out as a string of 0/1 bytes; every width-th byte of it is one bit
    of every value, so int.from_bytes of that strided slice holds that bit of each value in
    its own byte. Shifting and adding the slices assembles all values at once, one byte per
    value (two bytes above 8 bits, combined through an unsigned-short array).
    """
    if width == 0 or count == 0:
        return [0] * count
    if width > 16 or array("H").itemsize != 2:
        return _uints(buf, bitpos, width, count)
    nb = width * count
    sb = format(_bits(buf, bitpos, nb), "0%db" % nb).encode().translate(_T01)
    lo_w = min(width, 8)
    hi_w = width - lo_w
    lo = 0
    for t in range(lo_w):
        lo += int.from_bytes(sb[hi_w + t::width], "big") << (lo_w - 1 - t)
    lo_b = lo.to_bytes(count, "big")
    if not hi_w:
        return list(lo_b)
    hi = 0
    for t in range(hi_w):
        hi += int.from_bytes(sb[t::width], "big") << (hi_w - 1 - t)
    pair = bytearray(2 * count)
    pair[0::2] = hi.to_bytes(count, "big")
    pair[1::2] = lo_b
    arr = array("H", bytes(pair))
    if sys.byteorder == "little":
        arr.byteswap()
    return arr.tolist()


def _masks(w: int, n: int) -> list:
    """Bit-plane masks for n values of w bits: for every bit b of a value, the mask of that
    bit in all values, and in the values whose index (counted from the last value) has bit t set."""
    m = _MASKS.get((w, n))
    if m is None:
        if len(_MASKS) > 4000:
            _MASKS.clear()
        full = (1 << (w * n)) - 1
        unit = full // ((1 << w) - 1)          # bit 0 of every value
        planes, t = [], 0
        while (1 << t) < n:
            span = 1 << t
            blk = (((1 << (w * span)) - 1) // ((1 << w) - 1)) << (w * span)
            period = 2 * span * w
            reps = -(-n // (2 * span))
            planes.append(blk * (((1 << (period * reps)) - 1) // ((1 << period) - 1)) & full)
            t += 1
        m = _MASKS[(w, n)] = [(unit << b, [q << b for q in planes]) for b in range(w)]
    return m


def _group_sums(buf: bytes, bitpos: int, w: int, n: int):
    """(sum of v, sum of j * v) for the n w-bit values at bitpos, j = 0..n-1 in storage order."""
    big = _bits(buf, bitpos, w * n)
    if w > _POP_W or n > _POP_N:
        mask = (1 << w) - 1
        v = [(big >> s) & mask for s in range(w * (n - 1), -1, -w)]
        return sum(v), sum(map(mul, v, range(n)))
    s0 = rev = 0
    for b, (u, planes) in enumerate(_masks(w, n)):
        s0 += (big & u).bit_count() << b
        for t, q in enumerate(planes):
            rev += (big & q).bit_count() << (b + t)
    return s0, (n - 1) * s0 - rev            # rev counts j from the last value


def values_at(sec5: bytes, sec7: bytes, indices: Iterable[int]) -> Dict[int, Optional[float]]:
    """{storage index: value} for a few points, identical to decode() at those points.

    With second-order spatial differencing, f(0) = i1, f(1) = i2 and
    f(k) = 2 f(k-1) - f(k-2) + d(k) with d(k) = packed(k) + minsd, so

        f(n) = i1 + n (i2 - i1) + (n + 1) A - B,   A = sum d(k), B = sum k d(k), k = 2..n

    (first order: f(n) = i1 + A, k = 1..n). A and B are added up group by group: a group of
    constant values (width 0) adds in closed form, and for the others the sum and index-weighted
    sum of the packed values come from popcounts of bit-plane masks, so no value is unpacked
    one at a time and no float is built except at the requested points. Fields with missing
    values (management 1 or 2) are decoded in full instead.
    """
    want = sorted(set(int(i) for i in indices))
    if not want:
        return {}
    p = drs_params(sec5)
    if want[0] < 0 or want[-1] >= p["npts"]:
        raise IndexError(f"storage index outside 0..{p['npts'] - 1}")
    if p["missing"] in (1, 2):
        vals = decode(sec5, sec7, stop=want[-1] + 1)
        return {i: vals[i] for i in want}
    buf = sec7[5:]
    pos = 0
    order = p.get("order", 0) if p["tmpl"] == 3 else 0
    if order not in (0, 1, 2):
        raise ValueError(f"spatial differencing order {order} is not supported")
    i1 = i2 = minsd = 0
    if order:
        nb = p["extra_octets"] * 8
        i1 = _sm(_bits(buf, pos, nb), nb); pos += nb
        if order == 2:
            i2 = _sm(_bits(buf, pos, nb), nb); pos += nb
        minsd = _sm(_bits(buf, pos, nb), nb); pos += nb
    ng = p["ng"]
    tables = []
    for width in (p["nbits"], p["bits_width"], p["bits_len"]):
        tables.append(_uints_fast(buf, pos, width, ng))
        pos = ((pos + width * ng) + 7) & ~7
    refs, wtab, ltab = tables
    rw, rl, li, last = p["ref_width"], p["ref_len"], p["len_incr"], ng - 1
    got: Dict[int, int] = {}
    t, n = 0, want[0]
    k0 = A = B = 0
    for g in range(ng):
        ln = p["last_len"] if g == last else rl + ltab[g] * li
        w = wtab[g] + rw
        k1 = k0 + ln
        r = refs[g] + minsd
        while n < k1:                      # a requested point in this group
            if not order:
                got[n] = refs[g] + (_bits(buf, pos + (n - k0) * w, w) if w else 0)
            elif n < order:
                got[n] = i1 if n == 0 else i2
            else:
                a = max(k0, order)
                m = n - a + 1
                s0, s1 = _group_sums(buf, pos + (a - k0) * w, w, m) if w else (0, 0)
                An = A + m * r + s0
                Bn = B + r * (a + n) * m // 2 + a * s0 + s1
                got[n] = i1 + n * (i2 - i1) + (n + 1) * An - Bn if order == 2 else i1 + An
            t += 1
            if t == len(want):
                bscale, dscale, R = 2.0 ** p["E"], 10.0 ** -p["D"], p["R"]
                return {i: (R + got[i] * bscale) * dscale for i in want}
            n = want[t]
        if order:
            a = max(k0, order)
            if a < k1:
                m = k1 - a
                A += m * r
                B += r * (a + k1 - 1) * m // 2
                if w:
                    s0, s1 = _group_sums(buf, pos + (a - k0) * w, w, m)
                    A += s0
                    B += a * s0 + s1
        pos += w * ln
        k0 = k1
    raise IndexError("storage index beyond the last group")
