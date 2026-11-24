"""Storm-days from SNOTEL hourly data (TUNING_PLAN.md section 4).

A storm-day D is the 24 hours from 12Z on D to 12Z on D+1 (04:00 to 04:00 PST). It counts
when snow water rises by at least THRESHOLD_IN at any of the chosen sites.

Each 04:00 PST value is the median of the raw hourly readings from 02:00 to 06:00 PST, after
the quality-control rules found on Nov 24, 2026:
  * values flagged suspect (qc S) are dropped (they include all the impossible readings);
  * the 00:00 value is skipped: it is NRCS's edited daily value, not a raw reading, and can
    differ from the raw hours around it by 2 in.
The median makes one noisy hour harmless. Precipitation (PREC, accumulating) and snow depth
are anchored the same way; air temperature is summarized over the window.

`confirmed` separates storms from pillow noise: about 50 of the 425 raw storm-days in
WY2021-WY2027 had no gauge precipitation at SQV or WC3, mostly in March-May.
"""

import csv
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

THRESHOLD_IN = 0.25
ANCHOR_HOURS = (2, 3, 4, 5, 6)          # PST hours around 04:00 PST = 12Z
DEFAULT_SITES = ("SQV", "WC3")
CONFIRM_GAUGE_IN = 0.05   # a storm-day is confirmed when a trigger site's gauge rose this much ...
CONFIRM_SWE_IN = 0.10     # ... or at least two other sites gained this much snow water


def _f(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_site(nrcs_dir: Path, code: str) -> Dict[str, Dict[str, str]]:
    rows: Dict[str, Dict[str, str]] = {}
    for f in sorted((Path(nrcs_dir) / code).glob("WY*.csv")):
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                rows[r["time_pst"]] = r
    return rows


def _clean(r: Dict[str, str], col: str) -> Optional[float]:
    p = col.split("_")[0]
    if r.get(p + "_qc") == "S" or r["time_pst"].endswith(" 00:00"):
        return None
    return _f(r.get(col))


def anchor(rows: Dict[str, Dict[str, str]], day: date, col: str) -> Optional[float]:
    vals = []
    for h in ANCHOR_HOURS:
        r = rows.get(f"{day.isoformat()} {h:02d}:00")
        v = _clean(r, col) if r else None
        if v is not None:
            vals.append(v)
    return statistics.median(vals) if len(vals) >= 3 else None


def window(rows: Dict[str, Dict[str, str]], day: date) -> Dict[str, Any]:
    """Observed values for the 12Z-12Z window starting on `day`."""
    nxt = day + timedelta(days=1)
    out: Dict[str, Any] = {}
    for col, key in (("wteq_in", "swe"), ("prec_in", "precip"), ("snwd_in", "depth")):
        a, b = anchor(rows, day, col), anchor(rows, nxt, col)
        out[f"{key}_start_in"], out[f"{key}_end_in"] = a, b
        out[f"{key}_gain_in"] = round(b - a, 2) if a is not None and b is not None else None
    temps = []
    t = datetime(day.year, day.month, day.day, 4)
    for _ in range(25):
        r = rows.get(t.strftime("%Y-%m-%d %H:%M"))
        v = _clean(r, "tobs_f") if r else None
        if v is not None:
            temps.append(v)
        t += timedelta(hours=1)
    out["tobs_min_f"] = min(temps) if temps else None
    out["tobs_max_f"] = max(temps) if temps else None
    out["tobs_mean_f"] = round(sum(temps) / len(temps), 1) if temps else None
    out["tobs_hours"] = len(temps)
    sg, dg = out["swe_gain_in"], out["depth_gain_in"]
    out["rain_on_snow"] = bool(sg is not None and dg is not None and sg >= THRESHOLD_IN and dg < 0)
    return out


def storm_days(nrcs_dir: Path, sites=DEFAULT_SITES, threshold_in: float = THRESHOLD_IN,
               first: Optional[date] = None, last: Optional[date] = None,
               report_sites=None) -> List[Dict[str, Any]]:
    """Storm-days (any of `sites` gains >= threshold), with observations at every site in report_sites."""
    report_sites = list(report_sites or sites)
    data = {c: load_site(nrcs_dir, c) for c in set(report_sites) | set(sites)}
    times = sorted(t for c in sites for t in data[c])
    if not times:
        return []
    d0 = first or date.fromisoformat(times[0][:10])
    d1 = last or (date.fromisoformat(times[-1][:10]) - timedelta(days=1))
    out = []
    d = d0
    while d <= d1:
        obs = {c: window(data[c], d) for c in report_sites}
        trig = [c for c in sites if (obs[c]["swe_gain_in"] or 0) >= threshold_in]
        if trig:
            gauge = any((obs[c]["precip_gain_in"] or 0) >= CONFIRM_GAUGE_IN for c in sites)
            others = sum(1 for c in report_sites if c not in sites and (obs[c]["swe_gain_in"] or 0) >= CONFIRM_SWE_IN)
            out.append({"date": d.isoformat(), "window_utc": [f"{d.isoformat()}T12:00Z", f"{(d + timedelta(days=1)).isoformat()}T12:00Z"],
                        "triggered_by": trig, "confirmed": gauge or others >= 2,
                        "confirmed_by": ("gauge" if gauge else "") + ("+" if gauge and others >= 2 else "") + (f"{others} sites" if others >= 2 else ""),
                        "obs": obs})
        d += timedelta(days=1)
    return out
