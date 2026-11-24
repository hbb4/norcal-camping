"""Forecast archive and automatic verification against CDEC snow sensors.

Every pipeline run saves a compact snapshot of the hourly forecast at each
resort's snow-sensor site (SQV for Palisades, WC3 for Alpine) to
data/archive/. When a snapshot's 48-hour window has fully passed, it is
compared with the sensor's measured SWE (snow-water equivalent) and snow
depth change over the same window. Results are kept in
data/verification_history.json so past storms stay visible.

Caveats shown alongside the numbers:
* SWE from a snow pillow is the best measure of liquid that fell as snow;
  rain that drains through the pack is not captured.
* Depth change is settled depth: new snow compacts as it falls, so observed
  depth gain underestimates storm snowfall (typically by 20-40% over 48 h).
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

KEEP_DAYS = 21
MIN_SPACING_H = 3


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class ForecastVerifier:
    def __init__(self, data_dir: Path, cdec_client):
        self.archive_dir = Path(data_dir) / "archive"
        self.history_path = Path(data_dir) / "verification_history.json"
        self.resort_log_path = Path(data_dir) / "archive" / "resort_reports.json"
        self.cdec = cdec_client
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ archive
    def save_snapshot(self, data: Dict[str, Any]) -> Optional[Path]:
        issued = _parse(data["metadata"]["generated_at_utc"])
        existing = sorted(self.archive_dir.glob("forecast_*.json"))
        if existing:
            last = _parse(json.loads(existing[-1].read_text())["issued_utc"])
            if (issued - last) < timedelta(hours=MIN_SPACING_H):
                return None
        snap = {"issued_utc": issued.isoformat(), "resorts": {}}
        for rid, r in data.get("resorts", {}).items():
            om = r.get("sources", {}).get("open_meteo", {})
            sp = om.get("sensor_point")
            if om.get("status") != "success" or not sp:
                continue
            snap["resorts"][rid] = {"station": sp.get("id"), "elevation_ft": sp.get("elevation_ft"),
                                    "model": (sp.get("model") or (om.get("primary_model") or {}).get("label")),
                                    "hourly": sp.get("hourly", []), "proxy": None}
        if not snap["resorts"]:
            return None
        path = self.archive_dir / f"forecast_{issued.strftime('%Y%m%dT%H%MZ')}.json"
        path.write_text(json.dumps(snap))
        cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
        for p in existing:
            try:
                if _parse(json.loads(p.read_text())["issued_utc"]) < cutoff:
                    p.unlink()
            except Exception:
                pass
        return path

    def save_resort_report(self, rid: str, report: Dict[str, Any]) -> None:
        """Keep a log of the resort's reported new snow (one entry per resort per 3 h)."""
        log = self._load_resort_log()
        now = datetime.now(timezone.utc)
        mine = [e for e in log if e["resort_id"] == rid]
        if mine and now - _parse(mine[-1]["fetched_utc"]) < timedelta(hours=MIN_SPACING_H):
            return
        areas = report.get("snow_areas", {})
        log.append({"resort_id": rid, "fetched_utc": now.isoformat(), "report_updated": report.get("report_updated"),
                    "storm_total_in": report.get("storm_total_in"),
                    "areas": {t: {k: a.get(k) for k in ("elevation_ft", "new_24h_in", "new_72h_in", "new_7d_in", "base_depth_in")} for t, a in areas.items()}})
        cutoff = now - timedelta(days=KEEP_DAYS)
        log = [e for e in log if _parse(e["fetched_utc"]) >= cutoff]
        self.resort_log_path.write_text(json.dumps(log, indent=1))

    def _load_resort_log(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.resort_log_path.read_text())
        except Exception:
            return []

    def _attach_resort(self, entry: Dict[str, Any]) -> None:
        """Resort-reported new snow from the first report fetched within 5 days after the window end.
        The resort's 72 h / 7 d / storm totals are rolling and can include snow outside the window."""
        if entry.get("resort_report"):
            return
        end = _parse(entry["window_end_utc"])
        cands = [e for e in self._load_resort_log() if e["resort_id"] == entry["resort_id"]
                 and end <= _parse(e["fetched_utc"]) <= end + timedelta(days=5)]
        if not cands:
            return
        e = min(cands, key=lambda x: x["fetched_utc"])
        entry["resort_report"] = {"as_of_utc": e["fetched_utc"], "storm_total_in": e.get("storm_total_in"),
                                  "mid": e["areas"].get("mid"), "base": e["areas"].get("base")}

    # ------------------------------------------------------------------ verify
    def verify(self) -> Dict[str, Any]:
        """Verify the newest snapshot whose 48 h window is complete; return history."""
        history = self._load_history()
        now = datetime.now(timezone.utc)
        done = {(h["issued_utc"], h["resort_id"]) for h in history}
        candidates = []
        for p in sorted(self.archive_dir.glob("forecast_*.json")):
            try:
                snap = json.loads(p.read_text())
            except Exception:
                continue
            issued = _parse(snap["issued_utc"])
            if issued + timedelta(hours=49) <= now:
                candidates.append(snap)
        # newest complete snapshot + any snapshot that covered a storm and isn't verified yet
        for snap in candidates[-1:] + [s for s in candidates if s.get("seeded")]:
            for rid, fc in snap["resorts"].items():
                if (snap["issued_utc"], rid) in done:
                    continue
                result = self._verify_one(snap["issued_utc"], rid, fc)
                if result:
                    history.append(result)
                    done.add((snap["issued_utc"], rid))
        for h in history:
            self._attach_resort(h)
        history.sort(key=lambda h: h["issued_utc"], reverse=True)
        history = history[:40]
        self.history_path.write_text(json.dumps(history, indent=1))
        return {"latest": {rid: next((h for h in history if h["resort_id"] == rid), None) for rid in {h["resort_id"] for h in history}},
                "history": history}

    def _verify_one(self, issued_utc: str, rid: str, fc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        hourly = fc.get("hourly", [])[:48]
        if len(hourly) < 40:
            return None
        start, end = _parse(hourly[0]["time"]), _parse(hourly[-1]["time"]) + timedelta(hours=1)
        obs = self.cdec.fetch_window(fc["station"], start, end)
        if not obs or obs.get("swe_gain_in") is None:
            return None
        liq = sum(h["precip_in"] for h in hourly)
        snow_liq = sum(h["precip_in"] * (h.get("snow_fraction") if h.get("snow_fraction") is not None else 1) for h in hourly)
        snow = {
            "primary": round(sum(h.get("snowfall_rate_in_hr", 0) for h in hourly), 1),
            "kuchera": round(sum(h["precip_in"] * (h.get("snow_fraction") if h.get("snow_fraction") is not None else 1) * h["slr_kuchera"] for h in hourly if h.get("slr_kuchera") is not None), 1) if any(h.get("slr_kuchera") is not None for h in hourly) else None,
            "fixed_10": round(snow_liq * 10, 1),
        }
        swe = obs["swe_gain_in"]
        depth = obs.get("depth_gain_in")
        return {
            "resort_id": rid, "issued_utc": issued_utc, "station": fc["station"], "elevation_ft": fc.get("elevation_ft"),
            "model": fc.get("model"), "proxy": fc.get("proxy"),
            "window_start_utc": start.isoformat(), "window_end_utc": end.isoformat(),
            "forecast_liquid_in": round(liq, 2), "observed_swe_gain_in": round(swe, 2),
            "liquid_error_pct": round(100 * (liq - swe) / swe) if swe >= 0.1 else None,
            "forecast_snow_in": snow, "observed_depth_gain_in": depth,
            "observed_slr_settled": round(depth / swe, 1) if (depth and swe >= 0.3) else None,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _load_history(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.history_path.read_text())
        except Exception:
            return []

    # ------------------------------------------------------------------ seed
    def seed_from_legacy(self, legacy: Dict[str, Any], tier_map: Dict[str, Dict[str, str]]) -> Optional[Path]:
        """Turn an old full dataset (tier forecasts, no sensor point) into an archive
        snapshot, using the tier closest to each sensor's elevation as a proxy."""
        issued = _parse(legacy["metadata"]["generated_at_utc"])
        snap = {"issued_utc": issued.isoformat(), "seeded": True, "resorts": {}}
        for rid, m in tier_map.items():
            om = legacy["resorts"].get(rid, {}).get("sources", {}).get("open_meteo", {})
            tl = (om.get("elevation_timelines") or {}).get(m["tier"]) or []
            if not tl:
                continue
            snap["resorts"][rid] = {
                "station": m["station"], "elevation_ft": m["station_elev_ft"], "model": "Open-Meteo best_match (pre-change pipeline)",
                "proxy": f"{m['tier']} tier forecast at {m['tier_elev_ft']:,} ft used for the {m['station_elev_ft']:,} ft sensor; SLR was Kuchera",
                "hourly": [{"time": x["time"], "precip_in": x.get("precip_in", 0), "snowfall_rate_in_hr": x.get("snowfall_rate_in_hr", 0),
                            "slr": x.get("slr", 10), "slr_kuchera": x.get("slr", 10), "snow_fraction": x.get("snow_fraction", 1)} for x in tl],
            }
        path = self.archive_dir / f"forecast_{issued.strftime('%Y%m%dT%H%MZ')}.json"
        if snap["resorts"] and not path.exists():
            path.write_text(json.dumps(snap))
            return path
        return None
