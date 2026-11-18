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
        print(f"⚠️  Live network fetch encountered issues ({e}). Falling back to cached realistic storm profile...")
        data = generate_mock_live_snow_dataset()

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
        name = r_info.get("name")
        c = r_info.get("consensus_forecast", {})
        elev = r_info.get("elevations", {})
        sources = r_info.get("sources", {})

        exp_24h = c.get("next_24h_inches", {}).get("expected", 0)
        min_24h = c.get("next_24h_inches", {}).get("min", 0)
        max_24h = c.get("next_24h_inches", {}).get("max", 0)

        exp_48h = c.get("next_48h_inches", {}).get("expected", 0)
        tot_7d = c.get("next_7d_total_inches", 0)

        resort_rpt = sources.get("resort_official", {})
        cdec_rpt = sources.get("cdec_snotel", {})

        print(f"\n📍 {name.upper()}")
        print(f"   Elevation: Base {elev.get('base_ft'):,}' | Mid {elev.get('mid_ft'):,}' | Summit {elev.get('summit_ft'):,}' (Drop: {elev.get('vertical_drop_ft'):,}')")
        print(f"   🎯 Consensus Next 24h: {exp_24h}\" [Range: {min_24h}\" – {max_24h}\"]")
        print(f"   🎯 Consensus Next 48h: {exp_48h}\" | 7-Day Storm Total: {tot_7d}\"")
        print(f"   ⛷️  Powder Score: {c.get('powder_score')}/10 – {c.get('powder_rating')}")
        print(f"   💨 Wind Hold Risk: {c.get('wind_hold_risk', {}).get('status')} ({c.get('wind_hold_risk', {}).get('note')})")

        snow_24h_resort = resort_rpt.get("snow_24h_inches") or resort_rpt.get("snow_stake", {}).get("snow_24h_inches", "N/A")
        cdec_gain_24h = cdec_rpt.get("snow_depth_24h_delta_inches") or cdec_rpt.get("measurements", {}).get("snow_depth_24h_gain_inches", "N/A")
        cdec_depth = cdec_rpt.get("current_snow_depth_inches") or cdec_rpt.get("measurements", {}).get("snow_depth_current_inches", "N/A")

        print(f"   📊 Source Telemetry Comparison:")
        print(f"      • Resort Operations Reported 24h: {snow_24h_resort}\" (Base Depth: {resort_rpt.get('base_depth_base_inches', resort_rpt.get('snow_stake', {}).get('base_depth_inches', 'N/A'))}\")")
        print(f"      • CDEC Sensor ({cdec_rpt.get('station_id')}) 24h Gain: {cdec_gain_24h}\" (Total Depth: {cdec_depth}\")")
        print(f"      • Elevation Gradient Spread: {c.get('elevation_snow_gradient', {}).get('spread_inches')}\" difference (Base vs Summit)")

    # Print Road Conditions Summary
    road_conds = data.get("road_conditions", {})
    segments = road_conds.get("segments", [])
    print("\n" + "=" * 78)
    print("🚗 CALTRANS SIERRA HIGHWAY CHAIN CONTROLS & ROAD CLOSURES")
    print("=" * 78)
    for seg in segments:
        code = seg.get("status", "R-0")
        label = seg.get("status_label", "")
        name = seg.get("name", "")
        chk = seg.get("checkpoint", "")
        print(f"   • [{code}] {name}: {label}")
        print(f"     Checkpoint: {chk}")

    print("\n" + "=" * 78)
    print("To open the interactive dashboard, open dashboard.html or run:")
    print("    python3 server.py")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
