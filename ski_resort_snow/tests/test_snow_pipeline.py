"""Unit tests for Ski Resort Snow Pipeline & Caltrans Highway Integration."""

import unittest
import sys
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from collectors.aggregator import SnowAggregator
from collectors.caltrans_client import CaltransClient
from data.mock_live_data import generate_mock_live_snow_dataset


class TestSnowPipeline(unittest.TestCase):

    def test_mock_data_generation(self):
        data = generate_mock_live_snow_dataset()
        self.assertIn("resorts", data)
        self.assertIn("palisades_tahoe", data["resorts"])
        self.assertIn("alpine_meadows", data["resorts"])
        self.assertIn("road_conditions", data)

        pt = data["resorts"]["palisades_tahoe"]
        self.assertIn("consensus_forecast", pt)
        self.assertIn("sources", pt)
        self.assertGreater(pt["consensus_forecast"]["next_24h_inches"]["expected"], 0)

        # Check road segments
        segments = data["road_conditions"].get("segments", [])
        self.assertGreaterEqual(len(segments), 6)
        i80 = next((s for s in segments if "i80" in s["id"]), None)
        self.assertIsNotNone(i80)
        self.assertIn("polyline", i80)

    def test_aggregator_offline_run(self):
        aggregator = SnowAggregator(config_dir=BASE_DIR / "config")
        data = aggregator.run_aggregation(force_mock=True)

        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["resorts_monitored"], 2)

        alpine = data["resorts"]["alpine_meadows"]
        self.assertEqual(alpine["short_name"], "Alpine")
        self.assertIn("elevation_snow_gradient", alpine["consensus_forecast"])
        self.assertIn("road_conditions", data)

    def test_live_json_file_validity(self):
        live_path = BASE_DIR / "data" / "live_snow_data.json"
        self.assertTrue(live_path.exists())

        with open(live_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("resorts", data)
        self.assertIn("palisades_tahoe", data["resorts"])
        self.assertIn("alpine_meadows", data["resorts"])
        self.assertIn("road_conditions", data)

    def test_roads_config_validity(self):
        roads_path = BASE_DIR / "config" / "roads.json"
        self.assertTrue(roads_path.exists())

        with open(roads_path, "r", encoding="utf-8") as f:
            roads_data = json.load(f)

        routes = roads_data.get("monitored_routes", [])
        self.assertGreaterEqual(len(routes), 6)

        route_ids = [r["id"] for r in routes]
        self.assertIn("i80_donner_pass", route_ids)
        self.assertIn("sr89_north", route_ids)
        self.assertIn("sr89_south_emerald_bay", route_ids)

        for r in routes:
            self.assertTrue(len(r["polyline"]) >= 2, f"Route {r['id']} has invalid polyline")

    def test_caltrans_status_parsing(self):
        client = CaltransClient()
        self.assertIn("R-0", client.STATUS_DEFINITIONS)
        self.assertIn("R-1", client.STATUS_DEFINITIONS)
        self.assertIn("R-2", client.STATUS_DEFINITIONS)
        self.assertIn("R-3", client.STATUS_DEFINITIONS)
        self.assertIn("CLOSED", client.STATUS_DEFINITIONS)

        # Test severity ranking
        mock_recs = [
            {"ccStatus": {"status": "R-1"}},
            {"ccStatus": {"status": "R-2"}}
        ]
        highest = client._get_highest_severity(mock_recs)
        self.assertEqual(highest, "R-2")

        mock_closed = [
            {"ccStatus": {"status": "R-2"}},
            {"ccStatus": {"status": "CLOSED"}}
        ]
        highest_closed = client._get_highest_severity(mock_closed)
        self.assertEqual(highest_closed, "CLOSED")

    def test_hourly_chart_timeline_fields(self):
        data = generate_mock_live_snow_dataset()
        pt = data["resorts"]["palisades_tahoe"]
        om = pt["sources"]["open_meteo"]
        timeline = om.get("hourly_timeline", [])
        self.assertEqual(len(timeline), 48)

        step0 = timeline[0]
        self.assertIn("snowfall_rate_in_hr", step0)
        self.assertIn("cumulative_snow_inches", step0)
        self.assertIn("wind_mph", step0)
        self.assertIn("gust_mph", step0)
        self.assertIn("temp_f", step0)
        self.assertIn("wet_bulb_f", step0)
        self.assertIn("precip_phase", step0)
        self.assertIn("freezing_level_ft", step0)

        # Check elevation-specific timelines (summit, mid, base)
        elev_timelines = om.get("elevation_timelines", {})
        self.assertIn("summit", elev_timelines)
        self.assertIn("mid", elev_timelines)
        self.assertIn("base", elev_timelines)
        self.assertEqual(len(elev_timelines["summit"]), 48)
        self.assertEqual(len(elev_timelines["mid"]), 48)
        self.assertEqual(len(elev_timelines["base"]), 48)

        # Check atmospheric sounding (DGZ, precipitation phase analysis, mixing ratio)
        sounding = om.get("atmospheric_sounding", {})
        self.assertIn("dgz", sounding)
        self.assertIn("precipitation_phase_analysis", sounding)
        self.assertIn("moisture_and_dynamics", sounding)
        self.assertGreater(sounding["dgz"]["thickness_ft"], 1000)
        self.assertGreater(sounding["moisture_and_dynamics"]["surface_mixing_ratio_g_kg"], 0)

        # Check road shield labels and high-resolution geometry
        segments = data["road_conditions"].get("segments", [])
        i80 = next((s for s in segments if "i80" in s["id"]), None)
        self.assertIsNotNone(i80)
        self.assertIn("shield_label", i80)
        self.assertIn("shield_coords", i80)
        self.assertGreaterEqual(len(i80["polyline"]), 25)


if __name__ == "__main__":
    unittest.main()


class TestSoundingDiagnostics(unittest.TestCase):
    def test_kuchera_slr(self):
        from collectors.open_meteo_client import kuchera_slr
        self.assertAlmostEqual(kuchera_slr(271.16), 12.0)
        self.assertGreater(kuchera_slr(263.0), 18.0)   # cold column -> fluffy
        self.assertLess(kuchera_slr(274.0), 7.0)        # warm column -> dense
        self.assertGreaterEqual(kuchera_slr(300.0), 4.0)

    def test_wet_bulb_below_dry_bulb(self):
        from collectors.open_meteo_client import wet_bulb_stull_c
        self.assertLess(wet_bulb_stull_c(2.0, 60.0), 2.0)
        self.assertAlmostEqual(wet_bulb_stull_c(0.0, 99.0), 0.0, delta=0.5)

    def test_caltrans_real_schema_flatten(self):
        from collectors.caltrans_client import CaltransClient
        raw = {"data": [{"cc": {"inService": "true",
                                "location": {"route": "I-80", "nearbyPlace": "Kingvale", "locationName": "Donner Summit",
                                             "latitude": "39.31", "longitude": "-120.33", "direction": "East"},
                                "statusData": {"status": "R-2", "statusDescription": "Chains required"}}}]}
        recs = CaltransClient._flatten_records(raw)
        self.assertEqual(recs[0]["route"], "80")
        self.assertEqual(recs[0]["ccStatus"]["status"], "R-2")
        self.assertEqual(CaltransClient()._get_highest_severity(recs), "R-2")
