#!/usr/bin/env python3
"""Update Ski Resort Snow Data & Highway Road Conditions.

Runs the multi-source aggregation engine across all configured resorts (Palisades Tahoe
and Alpine Meadows) and Caltrans District 3/10 highway corridors, writing the unified
payload to data/live_snow_data.json and embedding it into dashboard.html.

Usage:
    python3 update_snow_data.py
    python3 update_snow_data.py --mock
    python3 update_snow_data.py --output custom_data.json
"""

import sys
import os
import argparse
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))
sys.path.insert(0, str(BASE_DIR))

from collectors.aggregator import SnowAggregator
from data.mock_live_data import generate_mock_live_snow_dataset


def main():
    parser = argparse.ArgumentParser(description="Fetch and aggregate live ski resort snow totals, forecasts, and Caltrans road conditions.")
    parser.add_argument("--mock", action="store_true", help="Use realistic offline storm and road condition simulation")
    parser.add_argument("--output", type=str, default=str(BASE_DIR / "data" / "live_snow_data.json"),
                        help="Output path for consolidated JSON")
    args = parser.parse_args()

    print("❄️  Starting Sierra Crest Snow Intelligence & Highway Ingestion Pipeline...")
    config_dir = BASE_DIR / "config"
    output_path = Path(args.output)

    aggregator = SnowAggregator(config_dir=config_dir)

    try:
        data = aggregator.run_aggregation(force_mock=args.mock)
    except Exception as e:
        print(f"Pipeline failed ({type(e).__name__}: {e}). Existing data was left unchanged.")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Embed data into dashboard.html for seamless offline file:// viewing
    dashboard_html_path = BASE_DIR / "dashboard.html"
    if dashboard_html_path.exists():
        with open(dashboard_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        json_str = json.dumps(data)
        script_tag = f"<script>window.__INITIAL_SNOW_DATA__ = {json_str};</script>"

        if "window.__INITIAL_SNOW_DATA__" in html_content:
            html_content = re.sub(
                r"<script>window\.__INITIAL_SNOW_DATA__\s*=\s*\{.*?\};</script>",
                lambda _: script_tag,
                html_content,
                flags=re.DOTALL
            )
        else:
            html_content = html_content.replace("</head>", f"  {script_tag}\n</head>")

        with open(dashboard_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    print(f"✅ Updated consolidated snow data saved to: {output_path}")
    print(f"✅ Embedded latest telemetry into: {dashboard_html_path}")

    print("\n" + "=" * 78)
    print("🏔️  SIERRA SNOW TOTALS & FORECAST CONSENSUS SUMMARY")
    print("=" * 78)

    for r_id, r_info in data.get("resorts", {}).items():
        c = r_info.get("consensus_forecast", {})
        elev = r_info.get("elevations", {})
        src = r_info.get("sources", {})
        om = src.get("open_meteo", {})
        summit = om.get("summit", {})
        cd = src.get("cdec_snotel", {})
        m = cd.get("measurements", {})
        rng = lambda d: f"{d.get('expected')} in (p10-p90 {d.get('min')}-{d.get('max')})" if d.get("min") is not None else f"{d.get('expected')} in"
        print(f"\n{r_info.get('name')}  (base {elev.get('base_ft'):,} / mid {elev.get('mid_ft'):,} / summit {elev.get('summit_ft'):,} ft)")
        print(f"   Sources: " + ", ".join(f"{k} {v.get('status')}" for k, v in src.items()))
        fmt = lambda b: f"{b.get('value')} in (p10-p90 {b.get('p10')}-{b.get('p90')})"
        for t in ("summit", "base"):
            tb = c.get(t) or {}
            print(f"   {t.title():6s} ({tb.get('elevation_ft')} ft) 24 h {fmt(tb.get('24h', {}))} · 48 h {fmt(tb.get('48h', {}))} · 7 d {fmt(tb.get('7d', {}))}")
        print(f"   Model: {c.get('source')} · NWS gridded (separate): {c.get('nws_gridded')}")
        print(f"   Summit liquid 48 h: {summit.get('liquid_48h_inches')} in · 7 d {summit.get('liquid_7d_inches')} in")
        print(f"   Peak summit gust 48 h: {om.get('peak_gust_summit_mph')} mph ({c.get('wind_hold_risk', {}).get('status')})")
        print(f"   CDEC {cd.get('station_id')}: depth {m.get('snow_depth_current_inches')} in, 24 h {m.get('snow_depth_24h_gain_inches')} in, SWE {m.get('swe_current_inches')} in")

    print("\n" + "=" * 78)
    print("🚗 CALTRANS SIERRA HIGHWAY CHAIN CONTROLS & ROAD CLOSURES")
    print("=" * 78)
    rc = data.get("road_conditions") or {}
    segments = rc.get("segments", [])
    print(f"   Caltrans feed: {'live' if rc.get('is_live_feed') else rc.get('status', 'unavailable')}, fetched {rc.get('fetched_at_utc')}")
    for seg in segments:
        code = seg.get("status", "R-0")
        label = seg.get("status_label", "")
        name = seg.get("name", "")
        chk = seg.get("checkpoint", "")
        print(f"   • [{code}] {name}: {label}")
        print(f"     Checkpoint: {chk}")

    print("\n" + "=" * 78)
    print("To open the dashboard with live refresh:")
    print("    python3 server.py --open")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
