"""Aggregator: runs every collector, reconciles sources and builds the dashboard payload.

Rules:
* No mock data in a live run. If a source fails, the previous successful
  data for that source is reused and marked ``status: "stale"`` with its
  original fetch time and the error; if there is none, the source is
  ``status: "error"``. Mock data is only used with --mock.
* Every source carries ``fetched_at_utc``.
* Each run is archived and verified against CDEC sensors (see verification.py).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Callable

try:
    from . import http_ssl  # noqa: F401  (fixes CA bundle before any request)
    from .open_meteo_client import OpenMeteoClient
    from .nws_client import NWSClient
    from .cdec_snotel_client import CDECSnotelClient
    from .resort_scraper import ResortScraper
    from .caltrans_client import CaltransClient
    from .raob_client import RaobClient
    from .verification import ForecastVerifier
except ImportError:
    import http_ssl  # noqa: F401
    from open_meteo_client import OpenMeteoClient
    from nws_client import NWSClient
    from cdec_snotel_client import CDECSnotelClient
    from resort_scraper import ResortScraper
    from caltrans_client import CaltransClient
    from raob_client import RaobClient
    from verification import ForecastVerifier

try:
    from data.mock_live_data import generate_mock_live_snow_dataset
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from data.mock_live_data import generate_mock_live_snow_dataset

M_PER_FT = 0.3048

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SnowAggregator:
    def __init__(self, config_dir: Path, data_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir) if data_dir else self.config_dir.parent / "data"
        self.resorts_cfg = self._load_json(self.config_dir / "resorts.json")
        self.roads_cfg = self._load_json(self.config_dir / "roads.json")

        self.open_meteo = OpenMeteoClient()
        self.nws = NWSClient()
        self.cdec = CDECSnotelClient()
        self.resort_scraper = ResortScraper()
        self.caltrans = CaltransClient()
        self.raob = RaobClient()
        self.verifier = ForecastVerifier(self.data_dir, self.cdec)

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _previous(self) -> Dict[str, Any]:
        try:
            return self._load_json(self.data_dir / "live_snow_data.json")
        except Exception:
            return {}

    @staticmethod
    def _keep_or_fail(new: Dict[str, Any], prev: Optional[Dict[str, Any]], ok: bool) -> Dict[str, Any]:
        if ok:
            new.setdefault("fetched_at_utc", _now())
            return new
        err = new.get("error_message") or new.get("status") or "fetch failed"
        if prev and prev.get("status") in ("success", "stale"):
            out = dict(prev)
            out["status"] = "stale"
            out["stale_reason"] = err
            out.setdefault("fetched_at_utc", prev.get("timestamp_utc"))
            return out
        new["status"] = "error"
        new["error_message"] = err
        new["fetched_at_utc"] = None
        return new

    # ------------------------------------------------------------------ roads only
    def refresh_roads(self, data: Dict[str, Any]) -> Dict[str, Any]:
        prev = data.get("road_conditions")
        roads = self.caltrans.get_road_conditions(self.roads_cfg.get("monitored_routes", []))
        live = bool(roads.get("is_live_feed"))
        roads["fetched_at_utc"] = _now() if live else None
        if live:
            data["road_conditions"] = roads
        elif prev:
            prev = dict(prev)
            prev["status"] = "stale"
            prev["stale_reason"] = "Caltrans CWWP2 feed did not respond"
            data["road_conditions"] = prev
        else:
            roads["status"] = "error"
            for seg in roads.get("segments", []):
                seg.update({"status": "UNKNOWN", "status_label": "No data (Caltrans feed unavailable)", "status_color": "#64748b",
                            "checkpoint": "", "description": "Caltrans CWWP2 did not respond."})
            data["road_conditions"] = roads
        return data

    # ------------------------------------------------------------------ full run
    def run_aggregation(self, force_mock: bool = False, progress: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
        if force_mock:
            return generate_mock_live_snow_dataset()
        say = progress or (lambda step, state: None)
        prev = self._previous()
        prev_resorts = prev.get("resorts", {})
        now = _now()
        out: Dict[str, Any] = {"metadata": {}, "resorts": {}}

        say("Caltrans chain controls", "running")
        out = self.refresh_roads({"road_conditions": prev.get("road_conditions"), **out})
        say("Caltrans chain controls", "done" if out["road_conditions"].get("is_live_feed") else "stale")

        say("Radiosondes (REV, OAK)", "running")
        soundings = {}
        for st in ("KREV", "KOAK"):
            r = self.raob.latest(st)
            soundings[st] = self._keep_or_fail(r, (prev.get("observed_soundings") or {}).get(st), r.get("status") == "success")
        out["observed_soundings"] = soundings
        say("Radiosondes (REV, OAK)", "done")

        for resort in self.resorts_cfg.get("resorts", []):
            rid, name = resort["id"], resort["short_name"]
            elevs = resort["elevations"]
            psrc = (prev_resorts.get(rid) or {}).get("sources", {})
            tiers = {t: {"lat": elevs[t]["latitude"], "lon": elevs[t]["longitude"],
                         "elevation_m": round(elevs[t]["feet"] * M_PER_FT), "note": elevs[t].get("location_note", "")}
                     for t in ("base", "mid", "summit")}
            cd = resort.get("cdec_station", {})
            sensor = {"id": cd.get("station_id"), "lat": cd.get("latitude"), "lon": cd.get("longitude"),
                      "elevation_m": round(cd.get("elevation_ft", 8000) * M_PER_FT)} if cd.get("latitude") else None

            say(f"{name}: models", "running")
            om = self.open_meteo.fetch_resort_forecast(tiers, sensor, progress=lambda m: say(f"{name}: {m}", "running"))
            om = self._keep_or_fail(om, psrc.get("open_meteo"), om.get("status") == "success")
            say(f"{name}: models", "done" if om["status"] == "success" else om["status"])

            say(f"{name}: NWS", "running")
            b, s = tiers["base"], tiers["summit"]
            nws = self.nws.fetch_resort_forecast(lat=b["lat"], lon=b["lon"], summit_lat=s["lat"], summit_lon=s["lon"])
            nws = self._keep_or_fail(nws, psrc.get("noaa_nws"), nws.get("status") == "success")
            say(f"{name}: NWS", "done" if nws["status"] == "success" else nws["status"])

            say(f"{name}: CDEC sensor", "running")
            cdec = self.cdec.fetch_station_telemetry(station_id=cd.get("station_id", "SQV"), elevation_ft=cd.get("elevation_ft", 8000),
                                                     station_name=cd.get("station_name", ""))
            if cdec.get("status") == "success":
                cdec.update({"latitude": cd.get("latitude"), "longitude": cd.get("longitude")})
            cdec = self._keep_or_fail(cdec, psrc.get("cdec_snotel"), cdec.get("status") == "success")
            say(f"{name}: CDEC sensor", "done" if cdec["status"] == "success" else cdec["status"])

            say(f"{name}: resort report", "running")
            report = self.resort_scraper.fetch_resort_report(rid)
            report = self._keep_or_fail(report, psrc.get("resort_official"), report.get("status") == "success")
            if report.get("status") == "success":
                try:
                    self.verifier.save_resort_report(rid, report)
                except Exception:
                    pass
            say(f"{name}: resort report", "done" if report["status"] == "success" else report["status"])

            out["resorts"][rid] = {
                "id": rid, "name": resort["name"], "short_name": name, "coordinates": resort["coordinates"],
                "elevations": {"base_ft": elevs["base"]["feet"], "mid_ft": elevs["mid"]["feet"], "summit_ft": elevs["summit"]["feet"],
                               "vertical_drop_ft": resort["stats"]["vertical_drop_ft"]},
                "consensus_forecast": self._calculate_consensus(resort, om, nws),
                "sources": {"resort_official": report, "open_meteo": om, "noaa_nws": nws, "cdec_snotel": cdec},
            }

        out["metadata"] = {
            "generated_at_utc": now,
            "completed_at_utc": _now(),
            "system_title": "Sierra Snow",
            "resorts_monitored": len(out["resorts"]),
            "road_segments_monitored": len((out.get("road_conditions") or {}).get("segments", [])),
        }

        say("Verification archive", "running")
        try:
            self.verifier.save_snapshot(out)
            out["verification"] = self.verifier.verify()
        except Exception as e:
            out["verification"] = {"error": str(e), "history": []}
        say("Verification archive", "done")
        return out

    # ------------------------------------------------------------------ consensus
    def _calculate_consensus(self, resort: Dict[str, Any], om: Dict[str, Any], nws: Dict[str, Any]) -> Dict[str, Any]:
        def num(v):
            return float(v) if isinstance(v, (int, float)) else None

        summit = om.get("summit") or {}
        om48, om24 = num(om.get("summit_48h_inches")), num(summit.get("snow_24h_inches"))
        nws48, nws24 = num(nws.get("forecast_48h_expected_inches")), num(nws.get("forecast_24h_expected_inches"))

        def blend(a, b):
            if a is not None and b is not None:
                return round(a * 0.55 + b * 0.45, 1)
            return round(a if a is not None else (b or 0.0), 1)

        exp48 = blend(om48, nws48)
        exp24 = blend(om24, nws24) if (om24 is not None or nws24 is not None) else round(exp48 * 0.55, 1)
        sg = nws.get("summit_grid") or {}
        nws_lbl = f"NWS {sg.get('wfo')} summit grid cell" if nws.get("snowfall_grid_used") == "summit" else f"NWS {nws.get('office', '')} base grid cell"
        blend_sources = f"55% model (summit) + 45% {nws_lbl}" if nws48 is not None else "model only (NWS gave no snowfall amount)"

        ens = summit.get("ensemble") or {}

        def spread(expected, key):
            st = ens.get(key)
            if not st:
                return None, None, "unavailable"
            return round(max(0.0, min(st["p10"], expected)), 1), round(max(st["p90"], expected), 1), f"ensemble p10-p90 ({ens.get('members')} members)"

        min48, max48, range_src = spread(exp48, "snow_48h")
        min24, max24, _ = spread(exp24, "snow_24h")

        peak_gust = num(om.get("peak_gust_summit_mph")) or 0.0
        wind_status = "HIGH" if peak_gust >= 65 else ("MODERATE" if peak_gust >= 45 else "LOW")

        # Powder index: 0.55 points per inch of the larger of next-24h or 60% of next-48h snow,
        # minus 1.2 for summit gusts > 60 mph or 0.5 for > 45 mph; clamped 1-10.
        score = min(10.0, max(exp24, exp48 * 0.6) * 0.55)
        score -= 1.2 if peak_gust > 60 else (0.5 if peak_gust > 45 else 0.0)
        score = round(max(1.0, min(10.0, score)), 1)

        return {
            "next_24h_inches": {"min": min24, "expected": exp24, "max": max24},
            "next_48h_inches": {"min": min48, "expected": exp48, "max": max48},
            "range_source": range_src,
            "blend_sources": blend_sources,
            "next_7d_total_inches": num(om.get("summit_7d_total_inches")),
            "powder_score": score,
            "powder_score_definition": "0.55 x max(24 h snow, 0.6 x 48 h snow) at the summit, minus 1.2 if summit gusts > 60 mph (0.5 if > 45); range 1-10",
            "wind_hold_risk": {"status": wind_status, "peak_gust_mph": peak_gust,
                               "affected_lifts": resort.get("wind_hold_vulnerable_lifts", []),
                               "criteria": "HIGH >= 65 mph summit gust, MODERATE 45-64, LOW < 45"},
        }
