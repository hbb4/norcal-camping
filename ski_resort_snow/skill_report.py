#!/usr/bin/env python3
"""Skill of the blend members at the SNOTEL pillows: days and whole storms, raw and bias-corrected,
with a categorical check, and how four blends would have done. Everything is scored out of sample
(leave one season out). Uses the cached Open-Meteo hindcasts from blend_weights.py --hindcast.

    python3 skill_report.py                 # short lead (most recent runs)
    python3 skill_report.py --lead-day 3    # after: python3 blend_weights.py --hindcast --lead-day 3
    python3 skill_report.py --md            # also write data/tuning/reports/skill_report[_dN].md

Samples (SQV and WC3 pillows; cold days only: site air temperature below 34 F all day, so the
pillow's 12Z-12Z snow-water gain is snowfall):
  day    one 12Z-12Z window; "wet" when forecast or observed >= 0.1 in
  storm  a run of consecutive confirmed storm-days (storm_days.json), forecast and observed summed;
         a storm counts at a site only if every day of it is cold there

Bias correction: one multiplier per model and pillow, sum(observed) / sum(forecast) over the wet days
of the other seasons, applied to the held-out season. Categorical: day >= 0.5 in and storm >= 1.0 in;
POD = hits / (hits + misses), FAR = false alarms / (hits + false alarms), CSI = hits / (hits + misses +
false alarms). Blends, each fitted on the other seasons and scored on the held-out one:
  equal raw            plain mean of the members
  equal corrected      mean of the bias-corrected members
  skill raw            weights 1/MAE of the raw members (what Skill blend (beta) uses today)
  skill corrected      weights 1/MAE of the corrected members, applied to corrected members
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import blend_weights as bw  # noqa: E402

STORM_DAYS = BASE_DIR / "data" / "tuning" / "storm_days.json"
REPORT_DIR = BASE_DIR / "data" / "tuning" / "reports"
COLD_F, WET_IN, DAY_THR, STORM_THR = 34.0, 0.1, 0.5, 1.0


def water_year(d):
    return d.year + (1 if d.month >= 10 else 0)


def load_series(om_id, site, lead_day=None, cache_dir=None):
    """All cached hourly values for one model and site at one lead, merged across seasons."""
    cache_dir = Path(cache_dir or bw.HINDCAST_DIR)
    out = {}
    for f in sorted(cache_dir.glob(f"{om_id}_{site}_*.json")):
        name = f.stem
        is_lead = "_d" in name.split(f"{om_id}_{site}_", 1)[1]
        if (lead_day is None and is_lead) or (lead_day is not None and not name.endswith(f"_d{lead_day}")):
            continue
        out.update(json.loads(f.read_text()))
    return out


def daily_records(series_by_model, rows, site):
    """Cold 12Z-12Z days with the observed gain and each model's forecast (None if missing)."""
    times = sorted({t[:10] for s in series_by_model.values() for t in s})
    recs = []
    for d in times:
        day = date.fromisoformat(d)
        t0 = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=24)
        a, b, tmax = bw.swe_at(rows, t0), bw.swe_at(rows, t1), bw.max_temp(rows, t0, t1)
        if a is None or b is None or tmax is None or tmax >= COLD_F:
            continue
        fc = {}
        for mid, s in series_by_model.items():
            vals = [s.get((t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")) for k in range(1, 25)]
            fc[mid] = None if any(v is None for v in vals) else sum(vals)
        recs.append({"site": site, "day": day, "wy": water_year(day), "obs": max(0.0, b - a), "fc": fc})
    return recs


def storms_from(storm_days):
    """Consecutive confirmed storm-days -> list of date lists."""
    ds = sorted(date.fromisoformat(d["date"]) for d in storm_days if d.get("confirmed"))
    out, cur = [], []
    for d in ds:
        if cur and (d - cur[-1]).days == 1:
            cur.append(d)
        else:
            if cur:
                out.append(cur)
            cur = [d]
    if cur:
        out.append(cur)
    return out


def storm_records(recs, storms, members):
    by = {(r["site"], r["day"]): r for r in recs}
    out = []
    for st in storms:
        for site in {r["site"] for r in recs}:
            rs = [by.get((site, d)) for d in st]
            if any(r is None for r in rs) or any(r["fc"].get(m) is None for r in rs for m in members):
                continue
            out.append({"site": site, "day": st[0], "wy": water_year(st[0]), "days": len(st),
                        "obs": sum(r["obs"] for r in rs), "fc": {m: sum(r["fc"][m] for r in rs) for m in members}})
    return out


def factors(train, members, pool_sites=False):
    """Multiplier per (model, site): sum(observed) / sum(forecast) over wet training days.

    pool_sites: one multiplier per model from all sites together (stored under every site)."""
    f = {}
    sites = sorted({r["site"] for r in train})
    for m in members:
        for site in sites:
            wet = [r for r in train if (pool_sites or r["site"] == site) and r["fc"].get(m) is not None and (r["fc"][m] >= WET_IN or r["obs"] >= WET_IN)]
            sf, so = sum(r["fc"][m] for r in wet), sum(r["obs"] for r in wet)
            f[(m, site)] = so / sf if sf > 0.05 else 1.0
    return f


def mae(pairs):
    return sum(abs(a - b) for a, b in pairs) / len(pairs) if pairs else None


def bias(pairs):
    return sum(a - b for a, b in pairs) / len(pairs) if pairs else None


def categorical(pairs, thr):
    h = sum(1 for f, o in pairs if f >= thr and o >= thr)
    m = sum(1 for f, o in pairs if f < thr and o >= thr)
    fa = sum(1 for f, o in pairs if f >= thr and o < thr)
    return {"pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None,
            "csi": h / (h + m + fa) if h + m + fa else None, "hits": h, "misses": m, "false_alarms": fa}


def evaluate(recs, srecs, members, pool_sites=False):
    """Leave one season out. Returns per-member and per-blend scores on held-out seasons.

    pool_sites: the bias correction uses one multiplier per model across both pillows."""
    seasons = sorted({r["wy"] for r in recs})
    if len(seasons) < 2:
        return None
    day_out = {k: [] for k in members}
    day_corr = {k: [] for k in members}
    storm_out = {k: [] for k in members}
    storm_corr = {k: [] for k in members}
    blends = {b: {"day": [], "storm": []} for b in ("equal raw", "equal corrected", "skill raw", "skill corrected")}
    factor_log = {}
    for s in seasons:
        train = [r for r in recs if r["wy"] != s]
        test = [r for r in recs if r["wy"] == s]
        stest = [r for r in srecs if r["wy"] == s]
        if not train or not test:
            continue
        f = factors(train, members, pool_sites)
        factor_log[s] = {f"{m}@{site}": round(v, 2) for (m, site), v in f.items()}
        # weights from training seasons (raw MAE, and MAE after in-sample correction)
        wet_tr = [r for r in train if any(r["fc"][m] >= WET_IN for m in members) or r["obs"] >= WET_IN]
        mae_raw = {m: mae([(r["fc"][m], r["obs"]) for r in wet_tr]) for m in members}
        mae_cor = {m: mae([(r["fc"][m] * f[(m, r["site"])], r["obs"]) for r in wet_tr]) for m in members}
        w_raw = {m: 1 / mae_raw[m] for m in members if mae_raw[m]}
        w_cor = {m: 1 / mae_cor[m] for m in members if mae_cor[m]}

        def blend(r, kind):
            if kind == "equal raw":
                return sum(r["fc"][m] for m in members) / len(members)
            if kind == "equal corrected":
                return sum(r["fc"][m] * f[(m, r["site"])] for m in members) / len(members)
            if kind == "skill raw":
                return sum(w_raw[m] * r["fc"][m] for m in w_raw) / sum(w_raw.values())
            return sum(w_cor[m] * r["fc"][m] * f[(m, r["site"])] for m in w_cor) / sum(w_cor.values())

        for r in test:
            for m in members:
                day_out[m].append((r["fc"][m], r["obs"]))
                day_corr[m].append((r["fc"][m] * f[(m, r["site"])], r["obs"]))
            for b in blends:
                blends[b]["day"].append((blend(r, b), r["obs"]))
        for r in stest:
            for m in members:
                storm_out[m].append((r["fc"][m], r["obs"]))
                storm_corr[m].append((r["fc"][m] * f[(m, r["site"])], r["obs"]))
            for b in blends:
                blends[b]["storm"].append((blend(r, b), r["obs"]))

    def wet(pairs):
        return [(a, b) for a, b in pairs if a >= WET_IN or b >= WET_IN]

    def row(dp, sp):
        return {"day_mae": mae(wet(dp)), "day_bias": bias(wet(dp)), "storm_mae": mae(sp), "storm_bias": bias(sp),
                "n_days": len(wet(dp)), "n_storms": len(sp), "day_cat": categorical(dp, DAY_THR), "storm_cat": categorical(sp, STORM_THR)}
    return {"seasons": seasons,
            "members_raw": {m: row(day_out[m], storm_out[m]) for m in members},
            "members_corrected": {m: row(day_corr[m], storm_corr[m]) for m in members},
            "blends": {b: row(v["day"], v["storm"]) for b, v in blends.items()},
            "factors_by_test_season": factor_log}


def fmt_table(title, rows):
    def n(v, p=2):
        return "  -  " if v is None else f"{v:+.{p}f}" if p == 2 and v < 0 else f"{v:.{p}f}"
    kw = max([18] + [len(k) for k in rows])
    lines = [title, f"  {'':{kw}} {'day MAE':>8} {'day bias':>9} {'storm MAE':>10} {'storm bias':>11}  {'day CSI':>7} {'POD':>5} {'FAR':>5}  {'storm CSI':>9}"]
    for k, r in sorted(rows.items(), key=lambda kv: (kv[1]["storm_mae"] if kv[1]["storm_mae"] is not None else 9)):
        c, sc = r["day_cat"], r["storm_cat"]
        lines.append(f"  {k:{kw}} {n(r['day_mae']):>8} {n(r['day_bias']):>9} {n(r['storm_mae']):>10} {n(r['storm_bias']):>11}  "
                     f"{n(c['csi']):>7} {n(c['pod']):>5} {n(c['far']):>5}  {n(sc['csi']):>9}")
    return "\n".join(lines)


def build(lead_day=None, cache_dir=None):
    members = bw.member_models()
    storm_days = json.loads(STORM_DAYS.read_text())["days"] if STORM_DAYS.exists() else []
    storms = storms_from(storm_days)
    recs = []
    for site in bw.HINDCAST_SITES:
        rows = bw.load_snotel(site)
        series = {m: load_series(om, site, lead_day, cache_dir) for m, om in members.items()}
        recs += daily_records({m: s for m, s in series.items() if s}, rows, site)
    out = {}
    six = list(members)
    rec6 = [r for r in recs if all(r["fc"].get(m) is not None for m in six)]
    out["six members (common days)"] = (evaluate(rec6, storm_records(rec6, storms, six), six), len(rec6))
    five = [m for m in members if m != "aifs"]
    rec5 = [r for r in recs if all(r["fc"].get(m) is not None for m in five)]
    out["five members, no AIFS (longer record)"] = (evaluate(rec5, storm_records(rec5, storms, five), five), len(rec5))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lead-day", type=int, choices=range(1, 8))
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    res = build(a.lead_day)
    lead = f"day-{a.lead_day} lead" if a.lead_day else "short lead"
    text = [f"Skill report, {lead}: SQV and WC3 pillows, cold days; all scores on held-out seasons (leave one season out). Inches; CSI/POD/FAR 0-1.",
            f"Day thresholds: wet >= {WET_IN} in for MAE, >= {DAY_THR} in for the categorical check; storm categorical >= {STORM_THR} in.", ""]
    for name, (r, n) in res.items():
        if not r:
            text.append(f"{name}: not enough seasons ({n} cold days).\n")
            continue
        text.append(f"== {name}: {n} cold site-days, seasons {', '.join('WY' + str(s) for s in r['seasons'])}")
        text.append(fmt_table("Members, raw", r["members_raw"]))
        text.append(fmt_table("Members, bias-corrected (multiplier fitted on the other seasons)", r["members_corrected"]))
        text.append(fmt_table("Blends", r["blends"]))
        last = r["factors_by_test_season"][r["seasons"][-1]] if r["factors_by_test_season"] else {}
        text.append("  Multipliers used for the latest season: " + ", ".join(f"{k} {v}" for k, v in sorted(last.items())))
        text.append("")
    out = "\n".join(text)
    print(out)
    if a.md:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / f"skill_report{f'_d{a.lead_day}' if a.lead_day else ''}.md"
        path.write_text("# Blend member skill at the pillows\n\n```\n" + out + "\n```\n")
        print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
