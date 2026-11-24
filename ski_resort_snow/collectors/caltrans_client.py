"""Caltrans CWWP2 Chain Control & Road Status Client.

Fetches real-time chain control restrictions (R-0, R-1, R-2, R-3) and road status
from the official Caltrans Commercial Wholesale Web Portal 2 (CWWP2) JSON feeds
for District 3 (Sacramento Valley / Sierra Passes) and District 10 (Central Sierra).
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


class CaltransClient:
    """Client for querying Caltrans CWWP2 real-time chain controls and road alerts."""

    D3_CC_URL = "https://cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json"
    D10_CC_URL = "https://cwwp2.dot.ca.gov/data/d10/cc/ccStatusD10.json"
    USER_AGENT = "SierraSnowDashboard/2.0 (outdoor-planning@example.com)"

    STATUS_DEFINITIONS = {
        "R-0": {
            "label": "Open / No Restrictions",
            "short_code": "R-0",
            "color": "#10b981",
            "description": "No chain restrictions currently in effect. Normal mountain driving conditions."
        },
        "R-1": {
            "label": "Chains Required (Snow Tires Exempt)",
            "short_code": "R-1",
            "color": "#f59e0b",
            "description": "Chains or traction devices required on all vehicles except passenger cars and light trucks with approved snow-tread tires on drive wheels."
        },
        "R-2": {
            "label": "Chains Required (4WD/AWD Exempt w/ Snow Tires)",
            "short_code": "R-2",
            "color": "#f97316",
            "description": "Chains required on all vehicles except four-wheel/all-wheel drive vehicles with approved snow-tread tires on all four wheels. 4WD vehicles must still carry chains."
        },
        "R-3": {
            "label": "Chains Required — No Exceptions",
            "short_code": "R-3",
            "color": "#ef4444",
            "description": "Chains required on ALL vehicles without exception. (Very rare; highway typically closed before R-3 is implemented)."
        },
        "NO FEED": {
            "label": "No live feed",
            "short_code": "NO FEED",
            "color": "#64748b",
            "description": "No live road-condition data for this road."
        },
        "CLOSED": {
            "label": "Highway Closed",
            "short_code": "CLOSED",
            "color": "#e11d48",
            "description": "Pass or highway corridor closed due to whiteouts, spinouts, avalanche mitigation, or severe accidents."
        }
    }

    def __init__(self, timeout_sec: int = 10):
        self.timeout_sec = timeout_sec

    def fetch_district_chain_controls(self, district: int = 3) -> List[Dict[str, Any]]:
        """Fetch CWWP2 chain-control records and flatten them.

        Real CWWP2 shape: {"data": [{"cc": {"location": {...route "SR-89"...},
        "statusData": {"status": "R-0", "statusDescription": ...}}}]}
        Returned records are flattened to
        {route: "89", nearbyPlace, locationName, lat, lon, direction, elevation,
         ccStatus: {status, description}}.
        """
        url = self.D3_CC_URL if district == 3 else self.D10_CC_URL
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []
        return self._flatten_records(data)

    @staticmethod
    def _flatten_records(data: Any) -> List[Dict[str, Any]]:
        items = data.get("data", []) if isinstance(data, dict) else (data or [])
        # Legacy / test shape: {"cwwp2": {"data": {"cc": [...]}}}
        if isinstance(data, dict) and "cwwp2" in data:
            items = [{"cc": x} for x in data["cwwp2"].get("data", {}).get("cc", [])]
        out = []
        for it in items:
            cc = it.get("cc", it) if isinstance(it, dict) else {}
            if str(cc.get("inService", "true")).lower() == "false":
                continue
            loc = cc.get("location", cc)
            st = cc.get("statusData", {}) or {}
            raw_route = str(loc.get("route", "")).upper()
            route = "".join(ch for ch in raw_route.split("-")[-1] if ch.isdigit()) or raw_route
            try:
                lat, lon = float(loc.get("latitude")), float(loc.get("longitude"))
            except (TypeError, ValueError):
                lat = lon = None
            status = st.get("status") or cc.get("ccStatus", {}).get("status", "R-0")
            out.append({
                "route": route,
                "nearbyPlace": loc.get("nearbyPlace", ""),
                "locationName": loc.get("locationName", ""),
                "direction": loc.get("direction", ""),
                "elevation": loc.get("elevation"),
                "lat": lat, "lon": lon,
                "ccStatus": {
                    "status": str(status).strip().upper(),
                    "description": st.get("statusDescription") or cc.get("ccStatus", {}).get("description", ""),
                },
            })
        return out

    def get_road_conditions(self, roads_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fetch live chain control feeds and match against monitored Tahoe highway segments."""
        now = datetime.now(timezone.utc)
        all_raw_cc = self.fetch_district_chain_controls(district=3) + self.fetch_district_chain_controls(district=10)
        self._road_index = {r["id"]: r for r in roads_config}

        is_live = len(all_raw_cc) > 0

        segments_status = []
        for road in roads_config:
            route_num = str(road.get("route", "")).strip().upper()
            seg_id = road["id"]

            feed = road.get("feed", "caltrans")
            matched_cc = [] if feed == "none" else self._find_matching_controls(route_num, seg_id, all_raw_cc)

            if feed == "none" or (feed == "partial" and not matched_cc):
                # no Caltrans coverage (Nevada roads): say so instead of defaulting to "open"
                status_code = "NO FEED"
                checkpoint = road.get("key_pass", "")
                direction = "Both Directions"
                desc = road.get("feed_note", "No live road-condition feed for this road.")
            elif matched_cc:
                # Use most restrictive control found on segment
                highest_status = self._get_highest_severity(matched_cc)
                primary_rec = matched_cc[0]
                status_code = highest_status
                worst = [r for r in matched_cc if r.get("ccStatus", {}).get("status", "") == highest_status] or matched_cc
                primary_rec = worst[0]
                checkpoint = " · ".join(sorted({(r.get("locationName") or r.get("nearbyPlace") or "") for r in worst if (r.get("locationName") or r.get("nearbyPlace"))}))[:160] or road.get("key_pass", "")
                direction = primary_rec.get("direction", "Both Directions")
                desc = primary_rec.get("ccStatus", {}).get("description") or self.STATUS_DEFINITIONS[status_code]["description"]
                if status_code == "R-0":
                    checkpoint = f"{len(matched_cc)} Caltrans checkpoints on this stretch, none active"
            else:
                # Default to R-0 or route configuration default
                status_code = "R-0"
                checkpoint = road.get("key_pass", "")
                direction = "Both Directions"
                desc = self.STATUS_DEFINITIONS["R-0"]["description"]

            info = self.STATUS_DEFINITIONS.get(status_code, self.STATUS_DEFINITIONS["R-0"])
            if feed == "partial" and matched_cc:
                checkpoint = f"{checkpoint} (California part only)" if checkpoint else "California part only"

            segments_status.append({
                "id": seg_id,
                "route": route_num,
                "name": road["name"],
                "common_name": road.get("common_name", road["name"]),
                "key_pass": road.get("key_pass", ""),
                "pass_elevation_ft": road.get("pass_elevation_ft", 0),
                "status": status_code,
                "status_label": info["label"],
                "status_color": info["color"],
                "direction": direction,
                "checkpoint": checkpoint,
                "description": desc,
                "critical_hazards": road.get("critical_hazards", ""),
                "coordinates": road.get("coordinates", {}),
                "shield_label": road.get("shield_label", road.get("common_name", "")),
                "shield_coords": road.get("shield_coords"),
                "checkpoints_matched": len(matched_cc) if matched_cc else 0,
                "feed": feed,
                "feed_note": road.get("feed_note", ""),
                "display": road.get("display", "monitored"),
                "polyline": road.get("polyline", [])
            })

        return {
            "source": "Caltrans CWWP2 District 3 & District 10",
            "is_live_feed": is_live,
            "updated_at_utc": now.isoformat(),
            "segments": segments_status
        }

    def _find_matching_controls(self, route_num: str, seg_id: str, cc_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Records on the same route number that sit within ~2 km of the segment's line."""
        import math
        road = getattr(self, "_road_index", {}).get(seg_id, {})
        line = road.get("polyline", [])[::10]
        matches = []
        for rec in cc_list:
            if str(rec.get("route", "")).strip().upper() != route_num:
                continue
            if not line or rec.get("lat") is None:
                matches.append(rec)
                continue
            lat, lon = rec["lat"], rec["lon"]
            kx = 111.32 * math.cos(math.radians(lat))
            d = min(math.hypot((lat - p[0]) * 110.57, (lon - p[1]) * kx) for p in line)
            if d <= 2.0:
                matches.append(rec)
        return matches

    def _get_highest_severity(self, records: List[Dict[str, Any]]) -> str:
        """Find highest restriction level among records (CLOSED > R-3 > R-2 > R-1 > R-0)."""
        severity_order = ["R-0", "R-1", "R-2", "R-3", "CLOSED"]
        highest_rank = 0

        for r in records:
            status_str = r.get("ccStatus", {}).get("status", "").strip().upper()
            if "CLOSED" in status_str:
                return "CLOSED"
            for rank, code in enumerate(severity_order):
                if code in status_str and rank > highest_rank:
                    highest_rank = rank

        return severity_order[highest_rank]
