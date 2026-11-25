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
import threading
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
    from .nbm_client import NBMClient
    from .grid_terrain import terrain_ft
    from .nbm_downscale import Downscaler
    from .verification import ForecastVerifier
    from .hrrr_slw import MODELS as SLW_MODELS, SLWClient
except ImportError:
    import http_ssl  # noqa: F401
    from open_meteo_client import OpenMeteoClient
    from nws_client import NWSClient
    from cdec_snotel_client import CDECSnotelClient
    from resort_scraper import ResortScraper
    from caltrans_client import CaltransClient
    from raob_client import RaobClient
    from nbm_client import NBMClient
    from grid_terrain import terrain_ft
    from nbm_downscale import Downscaler
    from verification import ForecastVerifier
    from hrrr_slw import MODELS as SLW_MODELS, SLWClient

try:
    from data.mock_live_data import generate_mock_live_snow_dataset
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from data.mock_live_data import generate_mock_live_snow_dataset

M_PER_FT = 0.3048

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ds_dist(ds, i: int, lat: float, lon: float) -> float:
    """km between box cell i and a lat/lon (same flat projection the downscaler uses)."""
    import math
    x = (lon + 120.25) * 111.0 * math.cos(math.radians(39.17))
    y = (lat - 39.17) * 111.0
    return math.hypot(ds.xy[i][0] - x, ds.xy[i][1] - y)


class SnowAggregator:
    def __init__(self, config_dir: Path, data_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir) if data_dir else self.config_dir.parent / "data"
        self.resorts_cfg = self._load_json(self.config_dir / "resorts.json")
        self.roads_cfg = self._load_json(self.config_dir / "roads.json")

        try:
            src_cfg = json.loads((Path(config_dir) / "sources.json").read_text())
        except Exception:
            src_cfg = {}
        # blends, and the precipitation correction the "precip_correction" blends use (neighborhood_hindcast.py fit)
        self.open_meteo = OpenMeteoClient(blends=src_cfg.get("blends"), precip_correction=src_cfg.get("precip_correction"))
        self.nws = NWSClient()
        self.cdec = CDECSnotelClient()
        self.resort_scraper = ResortScraper()
        self.caltrans = CaltransClient()
        self.raob = RaobClient()
        self.nbm = NBMClient(self.data_dir / "cache")
        self.slw = {m: SLWClient(self.data_dir / "cache", m) for m in SLW_MODELS}      # HRRR to 48 h, RRFS to 84 h
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

        # HRRR and RRFS supercooled liquid at the summits run beside everything else, one model after
        # the other (each uses a pool of worker processes). A new cycle is ~0.55 GB of byte-range
        # downloads for HRRR (~70 s) and ~1.2 GB for RRFS (~2.5 min); a cached one is a single request.
        slw_pts = {r["id"]: {"lat": r["elevations"]["summit"]["latitude"], "lon": r["elevations"]["summit"]["longitude"],
                             "elevation_ft": r["elevations"]["summit"]["feet"]} for r in self.resorts_cfg.get("resorts", [])}
        slw_res: Dict[str, Dict[str, Any]] = {m: {} for m in self.slw}

        def run_slw():
            for m, client in self.slw.items():
                try:
                    slw_res[m].update(client.fetch(slw_pts))
                except Exception as e:
                    slw_res[m].update({"status": "error", "error_message": f"{type(e).__name__}: {e}"})

        for m in self.slw:
            say(f"{SLW_MODELS[m]['name']} supercooled liquid", "running")
        slw_thread = threading.Thread(target=run_slw, name="slw-models", daemon=True)
        slw_thread.start()

        say("Caltrans chain controls", "running")
        out = self.refresh_roads({"road_conditions": prev.get("road_conditions"), **out})
        say("Caltrans chain controls", "done" if out["road_conditions"].get("is_live_feed") else "stale")

        say("Radiosonde (REV)", "running")
        soundings = {}
        for st in ("KREV",):
            r = self.raob.latest(st)
            soundings[st] = self._keep_or_fail(r, (prev.get("observed_soundings") or {}).get(st), r.get("status") == "success")
        out["observed_soundings"] = soundings
        say("Radiosonde (REV)", "done")

        say("NBM (NOAA)", "running")
        nbm_pts = {}
        for resort in self.resorts_cfg.get("resorts", []):
            for t, e in resort["elevations"].items():
                nbm_pts[f"{resort['id']}:{t}"] = {"lat": e["latitude"], "lon": e["longitude"]}
            c = resort.get("cdec_station", {})
            if c.get("latitude"):
                nbm_pts[f"{resort['id']}:sensor"] = {"lat": c["latitude"], "lon": c["longitude"]}
        try:
            nbm_all = self.nbm.fetch(nbm_pts, progress=lambda m: say(m, "running"))
        except Exception as e:
            nbm_all = {"status": "error", "error_message": f"{type(e).__name__}: {e}"}
        if nbm_all.get("status") == "success" and (nbm_all.get("box") or {}).get("latlon"):
            try:   # terrain height of every NBM cell in the box (cached permanently after the first lookup)
                nbm_all["terrain"] = terrain_ft([tuple(p) for p in nbm_all["box"]["latlon"]], self.config_dir / "grid_terrain.json",
                                                progress=lambda m: say(m, "running"))
            except Exception as e:
                nbm_all["terrain"] = {}
                say(f"NBM terrain lookup failed: {e}", "running")
        say("NBM (NOAA)", "done" if nbm_all.get("status") == "success" else "error")

        # NWS gridded snowfall at the cells around every tier, for the same elevation regression
        ds = Downscaler(nbm_all, nbm_all.get("terrain") or {}, NBMClient.to_steps) if nbm_all.get("box") else None
        ds = ds if ds and ds.ok else None
        nws_cells, cell_index = {}, {}
        if ds:
            say("NWS grid cells", "running")
            for resort in self.resorts_cfg.get("resorts", []):
                for t, e in resort["elevations"].items():
                    for i, (a, b) in enumerate(ds.ll):
                        info = (nbm_all["terrain"] or {}).get(f"{a:.4f},{b:.4f}")
                        if info and ds_dist(ds, i, e["latitude"], e["longitude"]) <= 6.0:
                            key = f"{info['wfo']}/{info['x']}/{info['y']}"
                            cell_index[key] = i
            try:
                nws_cells = self.nws.fetch_cells_snowfall({k: {} for k in cell_index}, self.data_dir / "cache" / "nws_cells.json",
                                                          progress=lambda m: say(m, "running"))
            except Exception as e:
                nws_cells = {}
                say(f"NWS grid cells failed: {e}", "running")
            say("NWS grid cells", "done" if nws_cells else "error")

        model_archive: Dict[str, Any] = {}   # every model's output per resort, for the per-model forecast archive
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
            nbm_r = None
            if nbm_all.get("status") == "success":
                nbm_r = {**{k: v for k, v in nbm_all.items() if k != "points"},
                         "points": {k.split(":", 1)[1]: v for k, v in nbm_all["points"].items() if k.startswith(rid + ":")}}
            else:
                nbm_r = nbm_all
            om_all = self.open_meteo.fetch_resort_forecast(tiers, sensor, progress=lambda m: say(f"{name}: {m}", "running"), nbm=nbm_r)
            models = om_all.get("models", {}) if om_all.get("status") == "success" else {}
            om = om_all["default"] if models else om_all
            om = self._keep_or_fail(om, psrc.get("open_meteo"), om.get("status") == "success")
            say(f"{name}: models", "done" if om["status"] == "success" else om["status"])

            say(f"{name}: NWS", "running")
            b, s = tiers["base"], tiers["summit"]
            nws = self.nws.fetch_resort_forecast(lat=b["lat"], lon=b["lon"], summit_lat=s["lat"], summit_lon=s["lon"])
            if ds and nws_cells and nws.get("status") == "success":
                nws["tier_estimates"] = self._nws_tiers(ds, nws_cells, cell_index, resort)
            nws = self._keep_or_fail(nws, psrc.get("noaa_nws"), nws.get("status") == "success")
            say(f"{name}: NWS", "done" if nws["status"] == "success" else nws["status"])

            say(f"{name}: CDEC sensor", "running")
            cdec = self.cdec.fetch_station_telemetry(station_id=cd.get("station_id", "SQV"), elevation_ft=cd.get("elevation_ft", 8000),
                                                     station_name=cd.get("station_name", ""))
            if cdec.get("status") == "success":
                cdec.update({"latitude": cd.get("latitude"), "longitude": cd.get("longitude"),
                             "location_note": cd.get("location_note", "")})
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

            # Every model to its own file (loaded on demand by the page), each with its own consensus;
            # the single models' precipitation-corrected versions beside them as <model>.corrected.json
            corrected = om_all.get("corrected_models", {}) if models else {}
            model_archive[rid] = {**models, **{f"{mid}_corrected": mo for mid, mo in corrected.items()}}
            model_dir = self.data_dir / "models" / rid
            model_dir.mkdir(parents=True, exist_ok=True)
            available = []
            for mid, mo in models.items():
                card = mo.get("model", {"id": mid})
                if mo.get("status") == "success":
                    mo["consensus_forecast"] = self._calculate_consensus(resort, mo, nws)
                    (model_dir / f"{mid}.json").write_text(json.dumps(mo))
                entry = {**card, "status": mo.get("status"), "summary": mo.get("summit_summary"), "error": mo.get("error_message")}
                co = corrected.get(mid)
                if mo.get("status") == "success" and co and co.get("status") == "success":
                    co["consensus_forecast"] = self._calculate_consensus(resort, co, nws)
                    (model_dir / f"{mid}.corrected.json").write_text(json.dumps(co))
                    entry["corrected_available"] = True
                    entry["corrected_summary"] = co.get("summit_summary")
                available.append(entry)
            if models:
                om["available_models"] = available
                om["scales"] = self._scales(models)
            elif psrc.get("open_meteo", {}).get("available_models"):
                om["available_models"] = psrc["open_meteo"]["available_models"]

            out["resorts"][rid] = {
                "id": rid, "name": resort["name"], "short_name": name, "coordinates": resort["coordinates"],
                "elevations": {"base_ft": elevs["base"]["feet"], "mid_ft": elevs["mid"]["feet"], "summit_ft": elevs["summit"]["feet"],
                               "vertical_drop_ft": resort["stats"]["vertical_drop_ft"]},
                "consensus_forecast": self._calculate_consensus(resort, om, nws),
                "priority_lifts": resort.get("priority_lifts", []),
                "sources": {"resort_official": report, "open_meteo": om, "noaa_nws": nws, "cdec_snotel": cdec},
            }

        slw_thread.join()
        for m, res in slw_res.items():          # sources.hrrr_slw, sources.rrfs_slw
            name, key = SLW_MODELS[m]["name"], f"{m}_slw"
            for rid, r in out["resorts"].items():
                new = (res.get("points") or {}).get(rid) if res.get("status") == "success" else None
                new = new or {"status": "error", "error_message": res.get("error_message") or f"no {name} data for this summit"}
                r["sources"][key] = self._keep_or_fail(new, ((prev_resorts.get(rid) or {}).get("sources") or {}).get(key),
                                                       new.get("status") == "success")
            say(f"{name} supercooled liquid", "done" if res.get("status") == "success" else "error")

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
            try:
                self.verifier.log_station_pairs(out)
                self.verifier.log_model_forecasts(model_archive, out)
            except Exception as e:
                say(f"station log failed: {e}", "running")
            out["verification"] = self.verifier.verify()
        except Exception as e:
            out["verification"] = {"error": str(e), "history": []}
        say("Verification archive", "done")
        return out

    # ------------------------------------------------------------------ consensus
    def _calculate_consensus(self, resort: Dict[str, Any], om: Dict[str, Any], nws: Dict[str, Any]) -> Dict[str, Any]:
        """Forecast numbers for the summary. Model values only (the selected model), with the
        ensemble 10th-90th percentile alongside. NWS gridded forecasts are reported separately
        and never blended in."""
        def num(v):
            return float(v) if isinstance(v, (int, float)) else None

        def tier(t):
            d = om.get(t) or {}
            e = d.get("ensemble") or {}
            out = {}
            for key, val in (("24h", d.get("snow_24h_inches")), ("48h", d.get("snow_48h_inches")), ("7d", d.get("snow_7d_total_inches"))):
                st = e.get({"24h": "snow_24h", "48h": "snow_48h", "7d": "snow_7d"}[key]) or {}
                out[key] = {"value": num(val), "p10": st.get("p10"), "p50": st.get("p50"), "p90": st.get("p90")}
            out["elevation_ft"] = d.get("elevation_ft")
            out["members"] = e.get("member_snow")
            return out

        summit, base = tier("summit"), tier("base")
        peak_gust = num(om.get("peak_gust_summit_mph")) or 0.0
        s24 = summit["24h"]["value"] or 0.0
        s48 = summit["48h"]["value"] or 0.0
        score = min(10.0, max(s24, s48 * 0.6) * 0.55)
        score -= 1.2 if peak_gust > 60 else (0.5 if peak_gust > 45 else 0.0)
        g = nws.get("grid") or {}
        sg = nws.get("summit_grid") or {}
        label = (om.get("model") or {}).get("label", "model")
        ens = (om.get("summit") or {}).get("ensemble") or {}
        return {
            "source": f"{label} only",
            "summit": summit, "base": base,
            # compatibility keys (summit)
            "next_24h_inches": {"min": summit["24h"]["p10"], "expected": s24, "max": summit["24h"]["p90"]},
            "next_48h_inches": {"min": summit["48h"]["p10"], "expected": s48, "max": summit["48h"]["p90"]},
            "next_7d_total_inches": summit["7d"]["value"],
            "range_source": f"ensemble p10-p90 ({ens.get('members')} members)" if ens.get("members") else "unavailable",
            "nws_gridded": {
                "base_cell": {"office": g.get("wfo"), "elevation_ft": g.get("elevation_ft"), "24h": g.get("next_24h_inches"),
                              "48h": g.get("next_48h_inches"), "total": g.get("total_snow_inches"), "through_utc": g.get("total_through_utc")},
                "summit_cell": {"office": sg.get("wfo"), "elevation_ft": sg.get("grid_elevation_ft"), "24h": sg.get("next_24h_inches"),
                                "48h": sg.get("next_48h_inches"), "total": sg.get("total_snow_inches"), "through_utc": sg.get("total_through_utc")} if sg else None,
                "tiers": (nws or {}).get("tier_estimates"),
            },
            "powder_score": round(max(1.0, min(10.0, score)), 1),
            "powder_score_definition": "0.55 x max(24 h snow, 0.6 x 48 h snow) at the summit (selected model), minus 1.2 if summit gusts > 60 mph (0.5 if > 45); range 1-10",
            "wind_hold_risk": {"status": "HIGH" if peak_gust >= 65 else ("MODERATE" if peak_gust >= 45 else "LOW"), "peak_gust_mph": peak_gust,
                               "affected_lifts": resort.get("wind_hold_vulnerable_lifts", []),
                               "criteria": "HIGH >= 65 mph summit gust, MODERATE 45-64, LOW < 45"},
        }

    @staticmethod
    def _nws_tiers(ds, cells: Dict[str, Any], index: Dict[str, int], resort: Dict[str, Any]) -> Dict[str, Any]:
        """NWS gridded snowfall moved to each tier's elevation with the NBM-style local regression
        on the NWS cells' own values (not on NBM's)."""
        out = {}
        for t, e in resort["elevations"].items():
            tier = {"elevation_ft": e["feet"]}
            for win, key in (("24h", "next_24h_inches"), ("48h", "next_48h_inches"), ("total", "total_snow_inches")):
                vals = {index[k]: c.get(key) for k, c in cells.items() if c and k in index and c.get(key) is not None}
                tier[win] = ds.regress_values(vals, e["latitude"], e["longitude"], e["feet"])
            thr = [c.get("total_through_utc") for c in cells.values() if c and c.get("total_through_utc")]
            tier["through_utc"] = min(thr) if thr else None
            out[t] = tier
        return out

    @staticmethod
    def _scales(models: Dict[str, Any]) -> Dict[str, Any]:
        """Axis limits shared by every model and elevation, so switching never rescales a chart."""
        cum = rate = gust = 0.0
        tmin, tmax = 200.0, -200.0
        dist = daily = 0.0
        lv_lo, lv_hi = 1e9, -1e9
        for mo in models.values():
            if mo.get("status") != "success":
                continue
            for x in mo.get("vertical_profile") or []:
                for k in ("snow_level_ft", "wet_bulb_zero_ft", "freezing_level_ft"):
                    v = x.get(k)
                    if v is not None:
                        lv_lo, lv_hi = min(lv_lo, v), max(lv_hi, v)
            for x in (mo.get("elevation_timelines") or {}).get("summit", []):
                v = x.get("snow_level_ft")
                if v is not None:
                    lv_lo, lv_hi = min(lv_lo, v), max(lv_hi, v)
            for t, tl in (mo.get("elevation_timelines") or {}).items():
                for x in tl:
                    cum = max(cum, x.get("cumulative_snow_inches") or 0, x.get("model_cumulative_inches") or 0)
                    rate = max(rate, x.get("snowfall_rate_in_hr") or 0)
                    gust = max(gust, x.get("gust_mph") or 0)
                    for k in ("temp_f", "free_air_temp_f"):
                        v = x.get(k)
                        if v is not None:
                            tmin, tmax = min(tmin, v), max(tmax, v)
            for t in ("base", "mid", "summit"):
                e = (mo.get(t) or {}).get("ensemble") or {}
                for c in e.get("cumulative_daily", []):
                    cum = max(cum, c.get("p90") or 0)
                ms = (e.get("member_snow") or {}).get("d7") or []
                if ms:
                    dist = max(dist, ms[int(0.95 * (len(ms) - 1))])
                dist = max(dist, (mo.get(t) or {}).get("snow_7d_total_inches") or 0)
                for d in (mo.get(t) or {}).get("daily_forecast") or []:     # day tiles: one scale for all
                    daily = max(daily, d.get("snow_p90") or 0, d.get("snowfall_inches") or 0)
        return {"cumulative_in": round(cum, 1), "rate_in_hr": round(rate, 2), "gust_mph": round(gust),
                "temp_f": [round(tmin), round(tmax)] if tmax > tmin else None, "distribution_in": round(dist, 1),
                "daily_in": round(daily, 1),
                "levels_ft": [round(lv_lo), round(lv_hi)] if lv_hi > lv_lo else None}
