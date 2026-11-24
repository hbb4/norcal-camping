"""Palisades Tahoe / Alpine Meadows resort report from the MtnPowder feed.

The resort's mountain-report page (palisadestahoe.com/mountain-information/
mountain-report) is drawn in the browser by a MtnPowder widget. The widget
reads its public configuration from

    https://v4.mtnfeed.com/resorts/palisades-tahoe.json   (resortIds, bearerToken)

and then the feed

    https://mtnpowder.com/feed/v3.json?bearer_token=...&resortId[]=61

This collector does the same, reading the token from the public config at run
time (nothing is hard-coded). Used with the user's approval.

One feed covers both mountains:
  Palisades snow/weather areas: BaseArea (6,200 ft), MidMountainArea (8,000 ft), SummitArea (Siberia Crest 8,700 ft)
  Alpine snow/weather areas:    Station4 (Alpine Base 6,950 ft), Station5 (Mid 8,120 ft), Station6 (Summit 8,543 ft)
  Lifts are grouped by mountain area; the areas below are split by side.
"""

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional

CONFIG_URL = "https://v4.mtnfeed.com/resorts/palisades-tahoe.json"
FEED_URL = "https://mtnpowder.com/feed/v3.json"
USER_AGENT = "SierraSnowDashboard/3.0"

SIDES = {
    "palisades_tahoe": {
        "snow_keys": {"base": "BaseArea", "mid": "MidMountainArea", "summit": "SummitArea"},
        "areas": ["Palisades Peak", "Emigrant Peak", "High Camp", "Granite Peak", "Snow King Peak", "KT Peak"],
    },
    "alpine_meadows": {
        "snow_keys": {"base": "Station4", "mid": "Station5", "summit": "Station6"},
        "areas": ["Summit Peak", "Scott/Lakeview Peak", "Sherwood Bowl"],
    },
}
WEATHER_KEYS = {
    "palisades_tahoe": {"base": "Base", "mid": "MidMountain", "summit": "Summit"},
    "alpine_meadows": {"base": "Station4", "mid": "Station5", "summit": "Station6"},
}


def _num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        s = str(v).strip()
        return None if s in ("", "--") else float(s)
    except ValueError:
        return None


def _elev_from_name(name: str) -> Optional[int]:
    m = re.search(r"el\.?\s*([\d,]+)", name or "")
    return int(m.group(1).replace(",", "")) if m else None


def _html_to_text(html: str) -> str:
    if not html or html.strip() == "--":
        return ""
    t = re.sub(r"(?i)<br\s*/?>", "\n", html)
    t = re.sub(r"(?i)</(div|p|li)>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "- ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = unescape(t)
    lines = [ln.strip() for ln in t.splitlines()]
    out, blank = [], False
    for ln in lines:
        if not ln:
            if not blank and out:
                out.append("")
            blank = True
        else:
            out.append(ln)
            blank = False
    return "\n".join(out).strip()


class ResortScraper:
    def __init__(self, timeout_sec: int = 20):
        self.timeout_sec = timeout_sec
        self._feed: Optional[Dict[str, Any]] = None
        self._feed_error: Optional[str] = None

    def _get(self, url: str) -> Dict[str, Any]:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as r:
            return json.loads(r.read().decode("utf-8"))

    def _load_feed(self) -> Optional[Dict[str, Any]]:
        """Fetch once per run; both resorts share the feed."""
        if self._feed is not None or self._feed_error:
            return self._feed
        try:
            cfg = self._get(CONFIG_URL)
            params = [("bearer_token", cfg["bearerToken"])] + [("resortId[]", str(r)) for r in cfg.get("resortIds", [])]
            feed = self._get(f"{FEED_URL}?{urllib.parse.urlencode(params)}")
            self._feed = (feed.get("Resorts") or [None])[0]
            if not self._feed:
                self._feed_error = "feed returned no resort"
        except Exception as e:
            self._feed_error = f"{type(e).__name__}: {e}"
        return self._feed

    def fetch_resort_report(self, resort_id: str) -> Dict[str, Any]:
        feed = self._load_feed()
        now = datetime.now(timezone.utc).isoformat()
        if not feed:
            return {"status": "error", "source": "MtnPowder feed (resort widget)", "error_message": self._feed_error, "fetched_at_utc": None}
        try:
            return self.parse(feed, resort_id, now)
        except Exception as e:
            return {"status": "error", "source": "MtnPowder feed (resort widget)", "error_message": f"parse: {e}", "fetched_at_utc": None}

    @staticmethod
    def parse(feed: Dict[str, Any], resort_id: str, fetched_at: str) -> Dict[str, Any]:
        side = SIDES[resort_id]
        sr = feed.get("SnowReport") or {}
        cc = feed.get("CurrentConditions") or {}

        snow_areas = {}
        for tier, key in side["snow_keys"].items():
            a = sr.get(key) or {}
            snow_areas[tier] = {
                "name": a.get("Name"), "elevation_ft": _elev_from_name(a.get("Name", "")),
                "base_depth_in": _num(a.get("BaseIn")), "new_24h_in": _num(a.get("Last24HoursIn")),
                "new_48h_in": _num(a.get("Last48HoursIn")), "new_72h_in": _num(a.get("Last72HoursIn")),
                "new_7d_in": _num(a.get("Last7DaysIn")), "since_lifts_closed_in": _num(a.get("SinceLiftsClosedIn")),
            }

        stations = {}
        for tier, key in WEATHER_KEYS[resort_id].items():
            w = cc.get(key) or {}
            if not w:
                continue
            stations[tier] = {
                "name": w.get("Name"), "elevation_ft": _elev_from_name(w.get("Name", "")),
                "observed_at": w.get("FeedSavedTime"), "temp_f": _num(w.get("TemperatureF")),
                "dew_point_f": _num(w.get("DewPointF")), "humidity_pct": _num(w.get("Humidity")),
                "wind_mph": _num(w.get("WindStrengthMph")), "gust_mph": _num(w.get("WindGustsMph")),
                "wind_dir": w.get("WindDirection"), "skies": w.get("Skies"),
            }

        lifts: List[Dict[str, Any]] = []
        for area in feed.get("MountainAreas") or []:
            if area.get("Name") not in side["areas"]:
                continue
            for lf in area.get("Lifts") or []:
                lifts.append({"name": lf.get("Name"), "area": area.get("Name"), "status": lf.get("Status"),
                              "type": lf.get("LiftType"), "updated": lf.get("UpdateDate")})
        trails_open = sum(a.get("OpenTrailsCount") or 0 for a in feed.get("MountainAreas") or [] if a.get("Name") in side["areas"])
        trails_total = sum(a.get("TotalTrailsCount") or 0 for a in feed.get("MountainAreas") or [] if a.get("Name") in side["areas"])
        open_states = ("open", "scheduled")
        base = snow_areas.get("base", {})
        mid = snow_areas.get("mid", {})

        return {
            "status": "success",
            "source": "Palisades Tahoe snow report (MtnPowder feed)",
            "fetched_at_utc": fetched_at,
            "report_updated": sr.get("LastUpdate"),
            "feed_updated": feed.get("LastUpdate"),
            "operating_status": feed.get("OperatingStatus"),
            "surface_condition": sr.get("BaseConditions"),
            "report_text": _html_to_text(sr.get("Report", "")),
            "snow_areas": snow_areas,
            "weather_stations": stations,
            "storm_total_in": _num(sr.get("StormTotalIn")),
            "season_total_in": _num(sr.get("SeasonTotalIn")),
            "annual_average_in": _num(sr.get("AnnualAverageSnowfallIn")),
            # convenience fields (mid-mountain first, then base)
            "snow_24h_inches": mid.get("new_24h_in") if mid.get("new_24h_in") is not None else base.get("new_24h_in"),
            "snow_72h_inches": mid.get("new_72h_in") if mid.get("new_72h_in") is not None else base.get("new_72h_in"),
            "snow_7d_inches": mid.get("new_7d_in") if mid.get("new_7d_in") is not None else base.get("new_7d_in"),
            "base_depth_base_inches": base.get("base_depth_in"),
            "base_depth_mid_inches": mid.get("base_depth_in"),
            "lifts": lifts,
            "lifts_open": sum(1 for l in lifts if (l["status"] or "").lower() in open_states),
            "lifts_total": len(lifts),
            "trails_open": trails_open,
            "trails_total": trails_total,
            "resort_wide": {"lifts_open": sr.get("TotalOpenLifts"), "lifts_total": sr.get("TotalLifts"),
                            "trails_open": sr.get("TotalOpenTrails"), "trails_total": sr.get("TotalTrails"),
                            "open_acres": _num(sr.get("OpenTerrainAcres")), "total_acres": _num(sr.get("TotalTerrainAcres")),
                            "groomed_trails": sr.get("GroomedTrails"), "grooming_active": sr.get("GroomingActive"),
                            "snowmaking_active": sr.get("SnowMakingActive")},
        }
