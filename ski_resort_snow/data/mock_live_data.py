"""Realistic Sierra Storm Telemetry & Road Conditions Data Generator.

Generates authentic, high-resolution storm cycle telemetry with realistic decimal variations,
multi-level elevation timelines (base, mid, summit), microphysics sounding parameters (DGZ,
mixing ratio, wet bulb, 700 hPa jet), multi-source benchmarks, and Caltrans road conditions
for offline development, testing, and sandbox environments.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from pathlib import Path
import json


def generate_mock_live_snow_dataset() -> Dict[str, Any]:
    return _augment_with_sounding_fields(_generate_base_mock())


def _generate_base_mock() -> Dict[str, Any]:
    """Generate a rich, authentic multi-source snow forecast and road condition dataset."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Load high-resolution road geometries from config/roads.json
    config_roads_path = Path(__file__).resolve().parent.parent / "config" / "roads.json"
    roads_config = []
    if config_roads_path.exists():
        with open(config_roads_path, "r", encoding="utf-8") as f:
            roads_config = json.load(f).get("monitored_routes", [])

    # Generate 48-hour hourly curves for Summit, Mid-Mountain, and Base
    pal_summit_timeline = []
    pal_mid_timeline = []
    pal_base_timeline = []

    alp_summit_timeline = []
    alp_mid_timeline = []
    alp_base_timeline = []

    cum_pal_summit = 0.0
    cum_pal_mid = 0.0
    cum_pal_base = 0.0

    cum_alp_summit = 0.0
    cum_alp_mid = 0.0
    cum_alp_base = 0.0

    for h in range(48):
        step_dt = now + timedelta(hours=h)
        time_str = step_dt.strftime("%Y-%m-%dT%H:00:00Z")

        # Atmospheric storm progression
        if h < 6:
            # Pre-frontal warm sector / rising moisture plume
            fl = 6950 - (h * 60)
            pop = 85

            # Rates
            r_pal_sum = round(0.42 + (h * 0.08), 2)
            r_pal_mid = round(0.32 + (h * 0.06), 2)
            r_pal_bas = round(0.18 + (h * 0.04), 2)

            r_alp_sum = round(0.40 + (h * 0.08), 2)
            r_alp_mid = round(0.34 + (h * 0.06), 2)
            r_alp_bas = round(0.26 + (h * 0.05), 2)

            # Temps & Wet Bulbs
            t_pal_sum = round(26.2 - (h * 0.2), 1)
            t_pal_mid = round(29.4 - (h * 0.2), 1)
            t_pal_bas = round(34.2 - (h * 0.3), 1)
            wb_pal_bas = round(32.8 - (h * 0.2), 1)

            t_alp_sum = round(25.8 - (h * 0.2), 1)
            t_alp_mid = round(28.6 - (h * 0.2), 1)
            t_alp_bas = round(32.2 - (h * 0.2), 1)
            wb_alp_bas = round(31.2 - (h * 0.2), 1)

            # Winds
            wind_sum = round(32.0 + (h * 2.5), 1)
            gust_sum = round(wind_sum * 1.58, 1)

            wind_mid = round(22.0 + (h * 1.8), 1)
            gust_mid = round(wind_mid * 1.50, 1)

            wind_bas = round(12.0 + (h * 1.2), 1)
            gust_bas = round(wind_bas * 1.45, 1)

            phase_pal_bas = "mix" if h < 3 else "snow"
            phase_label_pal_bas = "Rain / Snow Mix (Slush)" if h < 3 else "Wet Accumulating Snow"

            phase_alp_bas = "snow"
            phase_label_alp_bas = "100% Snow (High Base Advantage)"

        elif h < 22:
            # Core orographic atmospheric dump & crest gale surge
            peak_factor = 1.0 - abs(h - 14) / 10.0
            fl = round(6400 - (h - 6) * 75)
            pop = 98

            # Heavy snow rates
            r_pal_sum = round(1.35 + (peak_factor * 0.65), 2)
            r_pal_mid = round(1.05 + (peak_factor * 0.50), 2)
            r_pal_bas = round(0.68 + (peak_factor * 0.32), 2)

            r_alp_sum = round(1.28 + (peak_factor * 0.62), 2)
            r_alp_mid = round(1.10 + (peak_factor * 0.52), 2)
            r_alp_bas = round(0.88 + (peak_factor * 0.42), 2)

            # Temps
            t_pal_sum = round(21.4 - (h - 6) * 0.25, 1)
            t_pal_mid = round(25.2 - (h - 6) * 0.22, 1)
            t_pal_bas = round(29.8 - (h - 6) * 0.20, 1)
            wb_pal_bas = round(28.4 - (h - 6) * 0.20, 1)

            t_alp_sum = round(20.8 - (h - 6) * 0.25, 1)
            t_alp_mid = round(24.5 - (h - 6) * 0.22, 1)
            t_alp_bas = round(27.6 - (h - 6) * 0.20, 1)
            wb_alp_bas = round(26.5 - (h - 6) * 0.20, 1)

            # Winds
            wind_sum = round(42.0 + (peak_factor * 8.5), 1)
            gust_sum = round(wind_sum * 1.62, 1)

            wind_mid = round(28.0 + (peak_factor * 6.0), 1)
            gust_mid = round(wind_mid * 1.52, 1)

            wind_bas = round(15.0 + (peak_factor * 4.0), 1)
            gust_bas = round(wind_bas * 1.45, 1)

            phase_pal_bas = "snow"
            phase_label_pal_bas = "100% Snow"
            phase_alp_bas = "snow"
            phase_label_alp_bas = "100% Snow"

        elif h < 34:
            # Cold post-frontal instability showers
            fl = 5150
            pop = 75

            r_pal_sum = round(0.68 - ((h - 22) * 0.03), 2)
            r_pal_mid = round(0.52 - ((h - 22) * 0.02), 2)
            r_pal_bas = round(0.35 - ((h - 22) * 0.015), 2)

            r_alp_sum = round(0.65 - ((h - 22) * 0.03), 2)
            r_alp_mid = round(0.55 - ((h - 22) * 0.02), 2)
            r_alp_bas = round(0.42 - ((h - 22) * 0.015), 2)

            t_pal_sum = 18.2
            t_pal_mid = 21.8
            t_pal_bas = 26.5
            wb_pal_bas = 24.8

            t_alp_sum = 17.5
            t_alp_mid = 21.0
            t_alp_bas = 24.8
            wb_alp_bas = 23.2

            wind_sum = 28.5
            gust_sum = 46.0

            wind_mid = 19.5
            gust_mid = 32.0

            wind_bas = 11.0
            gust_bas = 19.0

            phase_pal_bas = "snow"
            phase_label_pal_bas = "100% Blower Snow"
            phase_alp_bas = "snow"
            phase_label_alp_bas = "100% Blower Snow"

        else:
            # Tapering flurries / clearing trend
            fl = 4900
            pop = 35

            r_pal_sum = 0.20
            r_pal_mid = 0.15
            r_pal_bas = 0.08

            r_alp_sum = 0.18
            r_alp_mid = 0.16
            r_alp_bas = 0.11

            t_pal_sum = 16.5
            t_pal_mid = 20.2
            t_pal_bas = 25.0
            wb_pal_bas = 23.5

            t_alp_sum = 15.8
            t_alp_mid = 19.5
            t_alp_bas = 23.5
            wb_alp_bas = 22.0

            wind_sum = 16.0
            gust_sum = 25.0

            wind_mid = 11.0
            gust_mid = 18.0

            wind_bas = 7.0
            gust_bas = 12.0

            phase_pal_bas = "dry" if h > 42 else "snow"
            phase_label_pal_bas = "Scattered Flurries / Dry" if h > 42 else "Light Snow"
            phase_alp_bas = "dry" if h > 42 else "snow"
            phase_label_alp_bas = "Scattered Flurries / Dry" if h > 42 else "Light Snow"

        # Accumulate
        cum_pal_summit += r_pal_sum
        cum_pal_mid += r_pal_mid
        cum_pal_base += r_pal_bas

        cum_alp_summit += r_alp_sum
        cum_alp_mid += r_alp_mid
        cum_alp_base += r_alp_bas

        # Common attributes
        snow_level = max(0, fl - 800)

        # Palisades Timelines
        pal_summit_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_pal_sum, 2),
            "cumulative_snow_inches": round(cum_pal_summit, 2),
            "temp_f": t_pal_sum,
            "wet_bulb_f": round(t_pal_sum - 1.2, 1),
            "dew_point_f": round(t_pal_sum - 3.5, 1),
            "precip_phase": "snow" if pop > 20 else "dry",
            "precip_phase_label": "100% Snow (Dry Blower)" if pop > 20 else "Dry / Flurries",
            "precip_probability": pop,
            "wind_mph": round(wind_sum, 1),
            "gust_mph": round(gust_sum, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

        pal_mid_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_pal_mid, 2),
            "cumulative_snow_inches": round(cum_pal_mid, 2),
            "temp_f": t_pal_mid,
            "wet_bulb_f": round(t_pal_mid - 1.0, 1),
            "dew_point_f": round(t_pal_mid - 3.0, 1),
            "precip_phase": "snow" if pop > 20 else "dry",
            "precip_phase_label": "100% Snow" if pop > 20 else "Dry / Flurries",
            "precip_probability": pop,
            "wind_mph": round(wind_mid, 1),
            "gust_mph": round(gust_mid, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

        pal_base_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_pal_bas, 2),
            "cumulative_snow_inches": round(cum_pal_base, 2),
            "temp_f": t_pal_bas,
            "wet_bulb_f": wb_pal_bas,
            "dew_point_f": round(t_pal_bas - 2.8, 1),
            "precip_phase": phase_pal_bas,
            "precip_phase_label": phase_label_pal_bas,
            "precip_probability": pop,
            "wind_mph": round(wind_bas, 1),
            "gust_mph": round(gust_bas, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

        # Alpine Timelines
        alp_summit_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_alp_sum, 2),
            "cumulative_snow_inches": round(cum_alp_summit, 2),
            "temp_f": t_alp_sum,
            "wet_bulb_f": round(t_alp_sum - 1.2, 1),
            "dew_point_f": round(t_alp_sum - 3.5, 1),
            "precip_phase": "snow" if pop > 20 else "dry",
            "precip_phase_label": "100% Snow (Dry Blower)" if pop > 20 else "Dry / Flurries",
            "precip_probability": pop,
            "wind_mph": round(wind_sum * 0.95, 1),
            "gust_mph": round(gust_sum * 0.94, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

        alp_mid_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_alp_mid, 2),
            "cumulative_snow_inches": round(cum_alp_mid, 2),
            "temp_f": t_alp_mid,
            "wet_bulb_f": round(t_alp_mid - 1.0, 1),
            "dew_point_f": round(t_alp_mid - 3.0, 1),
            "precip_phase": "snow" if pop > 20 else "dry",
            "precip_phase_label": "100% Snow" if pop > 20 else "Dry / Flurries",
            "precip_probability": pop,
            "wind_mph": round(wind_mid * 0.95, 1),
            "gust_mph": round(gust_mid * 0.94, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

        alp_base_timeline.append({
            "time": time_str,
            "snowfall_rate_in_hr": round(r_alp_bas, 2),
            "cumulative_snow_inches": round(cum_alp_base, 2),
            "temp_f": t_alp_bas,
            "wet_bulb_f": wb_alp_bas,
            "dew_point_f": round(t_alp_bas - 2.8, 1),
            "precip_phase": phase_alp_bas,
            "precip_phase_label": phase_label_alp_bas,
            "precip_probability": pop,
            "wind_mph": round(wind_bas * 0.95, 1),
            "gust_mph": round(gust_bas * 0.94, 1),
            "freezing_level_ft": fl,
            "snow_level_ft": snow_level
        })

    # Atmospheric Sounding & Microphysics Profiles
    sounding_palisades = {
        "dgz": {
            "base_elevation_ft": 10500,
            "top_elevation_ft": 14200,
            "thickness_ft": 3700,
            "relative_humidity_pct": 88,
            "status": "ACTIVE_BLOWER",
            "crystal_regime": "Stellar Dendrites & Needles (Optimal 14:1 to 18:1 SLR)",
            "description": "Deep 3,700-ft Dendritic Growth Zone saturated at 88% RH. Optimal temperature window (-12°C to -18°C) is heavily seeded with strong orographic upward vertical velocity, driving high-efficiency snowfall."
        },
        "precipitation_phase_analysis": {
            "current_freezing_level_ft": 5850,
            "effective_snow_level_ft": 5050,
            "base_village_elevation_ft": 6200,
            "summit_elevation_ft": 9050,
            "valley_mix_risk": "LOW RISK — Base village (6,200') is 1,150' above the effective snow level (5,050'). All snow expected after hour 3.",
            "phase_breakdown": {
                "summit": "100% Snow (Dry / Blower Powder)",
                "mid": "100% Snow (High-Efficiency Snowfall)",
                "base": "95% Snow (Wet Accumulating Snow / High Traction Impact)"
            }
        },
        "moisture_and_dynamics": {
            "surface_mixing_ratio_g_kg": 4.2,
            "moisture_category": "Ideal Pacific Orographic Sweet Spot (3.5 - 5.0 g/kg)",
            "crest_700hpa_jet_mph": 54.0,
            "peak_crest_gust_mph": 71.4,
            "crest_700hpa_wind_dir": "235° (SW - Ideal Cross-Barrier Angle)",
            "orographic_lift_index": "STRONG (Direct Sierra Crest Barrier Perpendicular Flow)"
        }
    }

    sounding_alpine = {
        "dgz": {
            "base_elevation_ft": 10500,
            "top_elevation_ft": 14200,
            "thickness_ft": 3700,
            "relative_humidity_pct": 89,
            "status": "ACTIVE_BLOWER",
            "crystal_regime": "Stellar Dendrites & Broad Branches (14:1 to 18:1 SLR)",
            "description": "Deep 3,700-ft DGZ saturated at 89% RH. Ward Peak and Alpine Bowl ridges funnel SW flow directly into the orographic convergence zone."
        },
        "precipitation_phase_analysis": {
            "current_freezing_level_ft": 5850,
            "effective_snow_level_ft": 5050,
            "base_village_elevation_ft": 6835,
            "summit_elevation_ft": 8637,
            "valley_mix_risk": "ZERO RISK — Alpine Meadows Base Lodge (6,835') sits safely 1,785' above the snow line. Pure snow throughout.",
            "phase_breakdown": {
                "summit": "100% Snow (Dry / Blower Powder)",
                "mid": "100% Snow (Cold Powder)",
                "base": "100% Snow (Base Lodge Snow Total ~4.8\" higher than Olympic Valley)"
            }
        },
        "moisture_and_dynamics": {
            "surface_mixing_ratio_g_kg": 4.1,
            "moisture_category": "Ideal Pacific Orographic Sweet Spot",
            "crest_700hpa_jet_mph": 52.0,
            "peak_crest_gust_mph": 68.5,
            "crest_700hpa_wind_dir": "230° (SW - Directly perpendicular to Ward Peak)",
            "orographic_lift_index": "STRONG (Optimal Ridge Ascent Velocity)"
        }
    }

    # Realistic road conditions across monitored Sierra corridors
    road_statuses = {
        "i80_donner_pass": {
            "status": "R-2",
            "status_label": "Chains Required (4WD/AWD Exempt w/ Snow Tires)",
            "status_color": "#f97316",
            "direction": "Eastbound & Westbound",
            "checkpoint": "Eastbound: Nyack to Truckee | Westbound: Truckee scales to Kingvale",
            "description": "Chains required on all vehicles except 4-wheel/all-wheel drive with snow tires on all 4 wheels. Heavy blowing snow over Donner Summit (7,239'). Visibility under 1/4 mile."
        },
        "sr89_north": {
            "status": "R-1",
            "status_label": "Chains Required (Snow Tires Exempt)",
            "status_color": "#f59e0b",
            "direction": "Both Directions",
            "checkpoint": "Truckee River Canyon (Mouse Creek to Tahoe City)",
            "description": "Chains required on all vehicles except passenger cars with snow tires on drive wheels. Slush and hard-packed snow between Palisades turnoff and Alpine Meadows turnoff."
        },
        "sr89_south_emerald_bay": {
            "status": "CLOSED",
            "status_label": "Highway Closed (Avalanche Control)",
            "status_color": "#e11d48",
            "direction": "Closed in Both Directions",
            "checkpoint": "D.L. Bliss State Park boundary to Emerald Bay Overlook",
            "description": "Highway 89 CLOSED over Emerald Bay due to active avalanche mitigation and rockfall on steep roadway cuts. No estimated time of reopening. Use East Shore (US-50 to SR-28) for transit."
        },
        "sr267_brockway": {
            "status": "R-2",
            "status_label": "Chains Required (4WD/AWD Exempt w/ Snow Tires)",
            "status_color": "#f97316",
            "direction": "Both Directions",
            "checkpoint": "Brockway Summit (Northstar Golf Course to Kings Beach)",
            "description": "Chains required on all vehicles except 4WD/AWD with snow tires on all 4 wheels. Steep winding grade over Brockway Summit (7,179')."
        },
        "sr28_north_shore": {
            "status": "R-1",
            "status_label": "Chains Required (Snow Tires Exempt)",
            "status_color": "#f59e0b",
            "direction": "Both Directions",
            "checkpoint": "Tahoe City to Stateline / Crystal Bay",
            "description": "Chains required on all vehicles except snow tires. Packed snow and slush along north shoreline."
        },
        "us50_echo_summit": {
            "status": "R-2",
            "status_label": "Chains Required (4WD/AWD Exempt w/ Snow Tires)",
            "status_color": "#f97316",
            "direction": "Eastbound & Westbound",
            "checkpoint": "Twin Bridges to Meyers (Echo Summit 7,377')",
            "description": "Chains required on all vehicles except 4WD/AWD with snow-tread tires on all four wheels. Tight hairpins and icy descent into Lake Tahoe basin."
        },
        "olympic_valley_road": {
            "status": "R-1",
            "status_label": "Chains Required (Snow Tires Exempt)",
            "status_color": "#f59e0b",
            "direction": "Westbound into Village",
            "checkpoint": "SR-89 Intersection to Village at Palisades Tahoe",
            "description": "Chains required. Placer County plows active. Heavy incoming ski traffic queuing for village parking."
        },
        "alpine_meadows_road": {
            "status": "R-2",
            "status_label": "Chains Required (4WD/AWD Exempt w/ Snow Tires)",
            "status_color": "#f97316",
            "direction": "Both Directions",
            "checkpoint": "River Ranch / SR-89 to Alpine Meadows Lodge",
            "description": "Chains required on all non-4WD vehicles. Winding alpine canyon road with active snow accumulation and avalanche control monitors."
        }
    }

    segments_list = []
    for road in roads_config:
        rid = road["id"]
        override = road_statuses.get(rid, {})
        segments_list.append({
            "id": rid,
            "route": road.get("route", ""),
            "name": road.get("name", ""),
            "common_name": road.get("common_name", ""),
            "key_pass": road.get("key_pass", ""),
            "pass_elevation_ft": road.get("pass_elevation_ft", 0),
            "shield_label": road.get("shield_label", road.get("common_name", "")),
            "shield_coords": road.get("shield_coords", [39.2, -120.2]),
            "status": override.get("status", "R-1"),
            "status_label": override.get("status_label", "Chains Required"),
            "status_color": override.get("status_color", "#f59e0b"),
            "direction": override.get("direction", "Both Directions"),
            "checkpoint": override.get("checkpoint", road.get("key_pass", "")),
            "description": override.get("description", "Winter traction conditions in effect."),
            "critical_hazards": road.get("critical_hazards", ""),
            "coordinates": road.get("coordinates", {}),
            "polyline": road.get("polyline", [])
        })

    return {
        "metadata": {
            "generated_at_utc": now_iso,
            "system_title": "Sierra Crest Ski Snow Forecast & Observation Engine",
            "active_storm_cycle": "Atmospheric River Wave #3 (Sierra Crest Cold Front)",
            "storm_cycle_dates": f"{now.strftime('%b %d')} – {(now + timedelta(days=3)).strftime('%b %d')}",
            "resorts_monitored": 2,
            "road_segments_monitored": len(segments_list)
        },
        "road_conditions": {
            "source": "Caltrans CWWP2 District 3 & District 10 (Simulated Storm Pass)",
            "is_live_feed": False,
            "updated_at_utc": now_iso,
            "summary": "Winter Storm Warning in effect: R-2 chain controls across I-80 Donner Pass and US-50 Echo Summit. Highway 89 Emerald Bay is CLOSED.",
            "segments": segments_list
        },
        "resorts": {
            "palisades_tahoe": {
                "id": "palisades_tahoe",
                "name": "Palisades Tahoe (Olympic Valley)",
                "short_name": "Palisades",
                "coordinates": {"lat": 39.1970, "lon": -120.2356},
                "elevations": {
                    "base_ft": 6200,
                    "mid_ft": 8010,
                    "summit_ft": 9050,
                    "vertical_drop_ft": 2850
                },
                "consensus_forecast": {
                    "next_24h_inches": {"min": 11.8, "expected": 16.4, "max": 21.6},
                    "next_48h_inches": {"min": 21.2, "expected": 29.8, "max": 38.6},
                    "next_7d_total_inches": 46.2,
                    "elevation_snow_gradient": {
                        "base_48h_forecast_inches": 16.4,
                        "mid_48h_forecast_inches": 25.2,
                        "summit_48h_forecast_inches": 31.8,
                        "spread_inches": 15.4,
                        "analysis": "Olympic Valley Base (6,200') vs Granite Peak (9,050'): ~15.4\" elevation spread expected. Upper mountain receives dry blower powder (14:1) while village level sees heavier accumulation (10:1)."
                    },
                    "powder_score": 8.4,
                    "powder_rating": "EPIC POWDER DAY IMMINENT",
                    "snow_quality_slr": "12.3:1 (Classic Sierra Cream)",
                    "wind_hold_risk": {
                        "status": "HIGH",
                        "affected_lifts": ["KT-22 Express", "Headwall Express", "Granite Chief", "Aerial Tram", "Base to Base Gondola"],
                        "note": "Crest gusts peaking at 71.4 mph will force upper mountain holds on KT-22 and the Base-to-Base Gondola during the peak frontal surge."
                    },
                    "atmospheric_sounding": sounding_palisades
                },
                "sources": {
                    "resort_official": {
                        "status": "success",
                        "source": "Palisades Tahoe Operations (Olympic Valley Desk)",
                        "updated_at": now_iso,
                        "snow_24h_inches": 12.5,
                        "snow_48h_inches": 24.8,
                        "snow_7d_inches": 38.4,
                        "season_total_inches": 218.6,
                        "base_depth_base_inches": 84.5,
                        "base_depth_summit_inches": 132.8,
                        "lifts_open": "23 / 29",
                        "trails_open": "148 / 170",
                        "surface_condition": "Deep Powder / Wind Packed",
                        "operations_note": "KT-22, Funitel, and Gold Coast turning. Base-to-Base Gondola on wind standby."
                    },
                    "open_meteo": {
                        "status": "success",
                        "source": "Open-Meteo High-Res Ensemble (ECMWF 9km / HRRR 3km)",
                        "updated_at": now_iso,
                        "base_48h_inches": 16.4,
                        "mid_48h_inches": 25.2,
                        "summit_48h_inches": 31.8,
                        "summit_7d_total_inches": 46.2,
                        "peak_gust_summit_mph": 71.4,
                        "avg_freezing_level_ft": 5850,
                        "elevation_timelines": {
                            "summit": pal_summit_timeline,
                            "mid": pal_mid_timeline,
                            "base": pal_base_timeline
                        },
                        "hourly_timeline": pal_summit_timeline,
                        "atmospheric_sounding": sounding_palisades
                    },
                    "noaa_nws": {
                        "status": "success",
                        "source": "NOAA / NWS Reno (REV Forecast Office)",
                        "updated_at": now_iso,
                        "active_hazards": [
                            {
                                "event": "Winter Storm Warning",
                                "severity": "Severe",
                                "headline": "Winter Storm Warning in effect until 10 PM PST for Greater Lake Tahoe",
                                "description": "Heavy snowfall and gale-force ridge winds expected. Snow accumulations of 20 to 34 inches above 7,000 feet, with 8 to 16 inches around lake level. Sierra crest winds gusting in excess of 75 mph.",
                                "instruction": "Travel will be very difficult to impossible across Donner Summit (I-80) and Echo Summit (US-50). Chain controls in effect. Carry winter survival equipment."
                            }
                        ],
                        "synoptic_discussion": "Deep moisture plume tapping subtropical Pacific moisture under strong orographic lift against the Northern Sierra Crest. Instability and steep lapse rates will produce snowfall rates up to 2.0 in/hr through midday.",
                        "forecast_24h_expected_inches": 16.5,
                        "forecast_48h_expected_inches": 28.2
                    },
                    "cdec_snotel": {
                        "status": "success",
                        "source": "CDEC / SNOTEL Sensor (SQV Gold Coast 8,010')",
                        "updated_at": now_iso,
                        "station_id": "SQV",
                        "elevation_ft": 8010,
                        "current_snow_depth_inches": 118.4,
                        "snow_depth_24h_delta_inches": 13.8,
                        "current_swe_inches": 34.62,
                        "swe_24h_delta_inches": 1.12,
                        "measured_slr": "12.3:1",
                        "sensor_temp_f": 26.4
                    }
                }
            },
            "alpine_meadows": {
                "id": "alpine_meadows",
                "name": "Alpine Meadows",
                "short_name": "Alpine",
                "coordinates": {"lat": 39.1644, "lon": -120.2386},
                "elevations": {
                    "base_ft": 6835,
                    "mid_ft": 7800,
                    "summit_ft": 8637,
                    "vertical_drop_ft": 1802
                },
                "consensus_forecast": {
                    "next_24h_inches": {"min": 11.5, "expected": 16.2, "max": 21.4},
                    "next_48h_inches": {"min": 20.8, "expected": 29.4, "max": 38.2},
                    "next_7d_total_inches": 45.4,
                    "elevation_snow_gradient": {
                        "base_48h_forecast_inches": 21.2,
                        "mid_48h_forecast_inches": 26.8,
                        "summit_48h_forecast_inches": 30.5,
                        "spread_inches": 9.3,
                        "analysis": "High Base Advantage: At 6,835', Alpine Meadows base is 635' higher than Olympic Valley. It stays below the freezing line throughout this storm cycle, resulting in ~4.8\" more accumulation at base lodge than Olympic Valley village."
                    },
                    "powder_score": 8.7,
                    "powder_rating": "STORM CHASER PARADISE",
                    "snow_quality_slr": "12.6:1 (Classic Sierra Cream)",
                    "wind_hold_risk": {
                        "status": "MODERATE_HIGH",
                        "affected_lifts": ["Summit 6", "Scott Chair", "Alpine Bowl Chair", "Base to Base Gondola"],
                        "note": "Summit 6 ridge exposed to southwest gale; Treeline Cirque and Roundhouse offer sheltered tree skiing."
                    },
                    "atmospheric_sounding": sounding_alpine
                },
                "sources": {
                    "resort_official": {
                        "status": "success",
                        "source": "Alpine Meadows Operations Desk",
                        "updated_at": now_iso,
                        "snow_24h_inches": 13.2,
                        "snow_48h_inches": 25.5,
                        "snow_7d_inches": 39.0,
                        "season_total_inches": 224.2,
                        "base_depth_base_inches": 92.4,
                        "base_depth_summit_inches": 138.5,
                        "lifts_open": "11 / 13",
                        "trails_open": "92 / 100",
                        "surface_condition": "Deep Powder / Wind Packed",
                        "operations_note": "Summit 6 on wind standby. Roundhouse and Treeline Cirque operating normally."
                    },
                    "open_meteo": {
                        "status": "success",
                        "source": "Open-Meteo High-Res Ensemble (ECMWF 9km / HRRR 3km)",
                        "updated_at": now_iso,
                        "base_48h_inches": 21.2,
                        "mid_48h_inches": 26.8,
                        "summit_48h_inches": 30.5,
                        "summit_7d_total_inches": 45.4,
                        "peak_gust_summit_mph": 68.5,
                        "avg_freezing_level_ft": 5850,
                        "elevation_timelines": {
                            "summit": alp_summit_timeline,
                            "mid": alp_mid_timeline,
                            "base": alp_base_timeline
                        },
                        "hourly_timeline": alp_summit_timeline,
                        "atmospheric_sounding": sounding_alpine
                    },
                    "noaa_nws": {
                        "status": "success",
                        "source": "NOAA / NWS Reno (REV Forecast Office)",
                        "updated_at": now_iso,
                        "active_hazards": [
                            {
                                "event": "Winter Storm Warning",
                                "severity": "Severe",
                                "headline": "Winter Storm Warning in effect until 10 PM PST for Greater Lake Tahoe",
                                "description": "Heavy snowfall and gale-force ridge winds expected. Snow accumulations of 20 to 34 inches above 7,000 feet.",
                                "instruction": "Travel will be very difficult to impossible across Donner Summit (I-80) and Echo Summit (US-50)."
                            }
                        ],
                        "synoptic_discussion": "Cold frontal boundary crossing the Sierra crest. Orographic enhancement along Ward Peak will sustain 1.5 to 2.0 in/hr rates through early afternoon.",
                        "forecast_24h_expected_inches": 16.2,
                        "forecast_48h_expected_inches": 27.8
                    },
                    "cdec_snotel": {
                        "status": "success",
                        "source": "CDEC / SNOTEL Sensor (Ward Creek #3 - WC3 6,750')",
                        "updated_at": now_iso,
                        "station_id": "WC3",
                        "elevation_ft": 6750,
                        "current_snow_depth_inches": 104.2,
                        "snow_depth_24h_delta_inches": 14.5,
                        "current_swe_inches": 31.8,
                        "swe_24h_delta_inches": 1.18,
                        "measured_slr": "12.6:1",
                        "sensor_temp_f": 25.8
                    }
                }
            }
        }
    }


def _augment_with_sounding_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add the fields the live Open-Meteo collector produces (vertical profile,
    SLR, snow fraction, precip-type chances, mixing ratio) to the mock so the
    dashboard renders the same panels offline."""
    import math
    for resort in data.get("resorts", {}).values():
        om = resort.get("sources", {}).get("open_meteo", {})
        tls = om.get("elevation_timelines", {})
        summit = tls.get("summit", [])
        profile = []
        for i, st in enumerate(summit):
            fl = st.get("freezing_level_ft") or 6000
            wbz = fl - 450
            # DGZ sits ~-12..-18 C; drift it with the freezing level
            dgz_base = fl + 6800
            heavy = st.get("snowfall_rate_in_hr", 0) >= 1.0
            profile.append({
                "time": st["time"],
                "freezing_level_ft": fl,
                "wet_bulb_zero_ft": wbz,
                "wbz_below_850hpa": False,
                "snow_level_ft": wbz - 500,
                "dgz_base_ft": dgz_base,
                "dgz_top_ft": dgz_base + (3600 if heavy else 2900),
                "dgz_thickness_ft": 3600 if heavy else 2900,
                "dgz_rh_pct": 92 if heavy else (80 if st.get("precip_probability", 0) > 50 else 55),
                "dgz_lift_cm_s": 28.0 if heavy else (9.0 if st.get("precip_probability", 0) > 50 else -4.0),
            })
        om["vertical_profile"] = profile
        elevs = resort.get("elevations", {})
        for tier, steps in tls.items():
            elev_ft = elevs.get(f"{tier}_ft", 7000)
            p_hpa = 1013.25 * (1 - 2.25577e-5 * elev_ft / 3.28084) ** 5.25588
            cum_model = 0.0
            for i, st in enumerate(steps):
                prof = profile[i] if i < len(profile) else {}
                wbz = prof.get("wet_bulb_zero_ft", 5500)
                frac = max(0.0, min(1.0, (elev_ft - (wbz - 1000)) / 1000.0))
                if st.get("precip_phase") == "mix":
                    frac = min(frac, 0.6)
                slr = 12.0 + (271.16 - (((st.get("temp_f", 28) - 32) * 5 / 9) + 273.15))
                slr = max(6.0, min(20.0, slr))
                rate = st.get("snowfall_rate_in_hr", 0.0)
                precip = rate / slr if frac > 0 else 0.05
                model = precip * 7.0 * frac
                cum_model += model
                dew_c = (st.get("dew_point_f", 25) - 32) * 5 / 9
                e = 6.112 * math.exp(17.67 * dew_c / (dew_c + 243.5))
                pop = st.get("precip_probability", 0)
                st.setdefault("precip_in", round(precip, 3))
                st.setdefault("slr", round(slr, 1))
                st.setdefault("snow_fraction", round(frac, 2))
                st.setdefault("model_snowfall_in_hr", round(model, 2))
                st.setdefault("model_cumulative_inches", round(cum_model, 2))
                st.setdefault("chance_snow_pct", round(pop * frac))
                st.setdefault("chance_rain_pct", round(pop * (1 - frac)))
                st.setdefault("mixing_ratio_g_kg", round(621.97 * e / (p_hpa - e), 2))
                st.setdefault("wind_dir_deg", 235)
                st.setdefault("wet_bulb_zero_ft", wbz)
                st["snow_level_ft"] = wbz - 500
    return data
