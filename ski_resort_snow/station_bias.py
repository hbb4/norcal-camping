#!/usr/bin/env python3
"""How far off is the model at the resort stations? (TUNING_PLAN.md, temperature)

    python3 station_bias.py                 all logged pairs
    python3 station_bias.py --model ecmwf_hres   one forecast model (nbm, ecmwf_hres, aifs, hrrr_gfs, icon,
                                                 ukmo, gem; runs from Nov 24, 2026 on log every model)

Every pipeline run logs the resort's base/mid/summit station readings next to the
selected model's next 24 hours at the matching tier (data/archive/station_pairs.jsonl):
2 m temperature and the free-air temperature from the model column. A reading is
paired with every earlier run whose 24 hours cover it, so each pair has a lead time.

For each resort and tier this prints the error (station minus model) of the 2 m value
and of the free-air value, split into night (18-06 PST) and day, and the coupling
weight c that best fits the station between them:

    T_station ~ T_free_air + c * (T_2m - T_free_air)

c near 0: the station behaves like free air (a ventilated slope or ridge above the
valley cold pool); c near 1: it behaves like the model's 2 m value (a sheltered valley
floor). A stable, tier-specific c is the "static" correction; how the hour-0 error
decays with lead time decides whether a "dynamic" one is worth applying.
"""

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PAIRS = BASE_DIR / "data" / "archive" / "station_pairs.jsonl"
PST = timezone(timedelta(hours=-8))


def parse_time(s):
    s = str(s)
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(model=None):
    runs = []
    if not PAIRS.exists():
        return runs
    for line in PAIRS.read_text().splitlines():
        try:
            runs.append(json.loads(line))
        except ValueError:
            continue
    return runs


def pairs(runs, model=None):
    """(resort, tier, lead_h, obs_f, t2m_f, free_air_f, obs_time_utc) for every reading x covering run."""
    obs = []   # (resort, tier, time, temp)
    fcs = []   # (resort, tier, start, temps, free_air, model)
    for r in runs:
        for rid, v in r.get("resorts", {}).items():
            for tier, x in (v.get("tiers") or {}).items():
                ob = x.get("obs") or {}
                if ob.get("temp_f") is not None and ob.get("observed_at"):
                    obs.append((rid, tier, parse_time(ob["observed_at"]).astimezone(timezone.utc), ob["temp_f"]))
                fc = x.get("fc") or {}
                mser = ((v.get("models") or {}).get(model) or {}).get(tier) if model else None
                if mser and mser.get("fc_start") and mser.get("temp_f"):        # any model, logged per run
                    fcs.append((rid, tier, parse_time(mser["fc_start"]).astimezone(timezone.utc), mser["temp_f"], mser.get("free_air_temp_f") or [], model))
                elif (not model or v.get("model") == model) and x.get("fc_start") and fc.get("temp_f"):   # the default model
                    fcs.append((rid, tier, parse_time(x["fc_start"]).astimezone(timezone.utc), fc["temp_f"], fc.get("free_air_temp_f") or [], v.get("model")))
    seen, out = set(), []
    for rid, tier, t_obs, temp in obs:
        if (rid, tier, t_obs) in seen:
            continue
        seen.add((rid, tier, t_obs))
        hour = t_obs.replace(minute=0, second=0, microsecond=0) + (timedelta(hours=1) if t_obs.minute >= 30 else timedelta())
        for frid, ftier, start, temps, fa, _ in fcs:
            if (frid, ftier) != (rid, tier):
                continue
            lead = int(round((hour - start).total_seconds() / 3600))
            if 0 <= lead < len(temps) and temps[lead] is not None:
                out.append((rid, tier, lead, temp, temps[lead], fa[lead] if lead < len(fa) else None, hour))
    return out


def stats(errs):
    if not errs:
        return "    -"
    n = len(errs)
    bias = sum(errs) / n
    mae = sum(abs(e) for e in errs) / n
    return f"{bias:+5.1f} / {mae:4.1f} (n {n})"


def coupling(rows):
    """Least-squares c in obs - fa = c * (t2m - fa)."""
    num = den = 0.0
    for _, _, _, ob, t2, fa, _ in rows:
        if fa is None:
            continue
        d = t2 - fa
        num += d * (ob - fa)
        den += d * d
    return (num / den) if den > 1.0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="only runs whose selected model is this id (e.g. nbm, hrrr_gfs)")
    a = ap.parse_args()
    runs = load(a.model)
    rows = pairs(runs, a.model)
    if not rows:
        print(f"No pairs{f' for {a.model}' if a.model else ''} yet in {PAIRS}. They are logged on every pipeline run "
              f"(python3 server.py refreshes hourly){'; every model is logged from Nov 24, 2026 on' if a.model else ''}.")
        return 1
    first = min(r[6] for r in rows).astimezone(PST)
    last = max(r[6] for r in rows).astimezone(PST)
    print(f"{len(runs)} runs, {len(rows)} station-forecast pairs, {first:%b %d %H:%M} to {last:%b %d %H:%M} PST")
    print("error = station minus model, bias / mean absolute error in F; night = 18:00-06:00 PST\n")
    print(f"{'resort':16} {'tier':7} {'2 m night':>20} {'2 m day':>20} {'free air night':>20} {'free air day':>20} {'c night':>8} {'c day':>6}")
    for rid in sorted({r[0] for r in rows}):
        for tier in ("base", "mid", "summit"):
            sel = [r for r in rows if r[0] == rid and r[1] == tier]
            if not sel:
                continue
            night = [r for r in sel if r[6].astimezone(PST).hour >= 18 or r[6].astimezone(PST).hour < 6]
            day = [r for r in sel if r not in night]
            e2 = lambda rs: [r[3] - r[4] for r in rs]
            ef = lambda rs: [r[3] - r[5] for r in rs if r[5] is not None]
            cn, cd = coupling(night), coupling(day)
            print(f"{rid:16} {tier:7} {stats(e2(night)):>20} {stats(e2(day)):>20} {stats(ef(night)):>20} {stats(ef(day)):>20} "
                  f"{'' if cn is None else f'{cn:8.2f}':>8} {'' if cd is None else f'{cd:6.2f}':>6}")
    print("\n2 m error by lead time (all resorts and tiers): bias / MAE")
    for lo, hi in ((0, 0), (1, 3), (4, 9), (10, 17), (18, 23)):
        sel = [r[3] - r[4] for r in rows if lo <= r[2] <= hi]
        print(f"  {lo:>2}-{hi:<2} h  {stats(sel)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
