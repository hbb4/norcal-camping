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


class TestSlrAndVerification(unittest.TestCase):
    def test_psychrometric_wet_bulb_between_dewpoint_and_temp(self):
        from collectors.open_meteo_client import wet_bulb_psychro_c, dewpoint_c
        for t, rh, p in [(-44, 20, 300), (-10, 60, 600), (0, 80, 750), (15, 50, 1000)]:
            td = dewpoint_c(t, rh)
            tw = wet_bulb_psychro_c(t, td, p)
            self.assertLessEqual(td - 0.01, tw)
            self.assertLessEqual(tw, t + 0.01)

    def test_habit_slr_peaks_in_dgz(self):
        from collectors.open_meteo_client import habit_slr
        self.assertGreater(habit_slr(-15), habit_slr(-5))
        self.assertGreater(habit_slr(-15), habit_slr(-25))
        self.assertEqual(habit_slr(2), habit_slr(0))

    def test_wind_factor_bounds(self):
        from collectors.open_meteo_client import wind_factor
        self.assertEqual(wind_factor(5), 1.0)
        self.assertAlmostEqual(wind_factor(35), 0.9)
        self.assertEqual(wind_factor(90), 0.75)

    def test_verification_compares_forecast_with_sensor(self):
        import tempfile
        from collectors.verification import ForecastVerifier

        class FakeCdec:
            def fetch_window(self, station, start, end):
                return {"swe_gain_in": 2.0, "depth_gain_in": 14.0}

        with tempfile.TemporaryDirectory() as d:
            v = ForecastVerifier(Path(d), FakeCdec())
            hourly = [{"time": f"2026-11-01T{h % 24:02d}:00Z".replace("T", f"T") , "precip_in": 0.05, "snowfall_rate_in_hr": 0.5,
                       "slr": 10, "slr_kuchera": 14, "snow_fraction": 1.0} for h in range(48)]
            for i, h in enumerate(hourly):
                h["time"] = f"2026-11-{1 + i // 24:02d}T{i % 24:02d}:00Z"
            r = v._verify_one("2026-11-01T00:00:00+00:00", "palisades_tahoe", {"station": "SQV", "hourly": hourly})
            self.assertAlmostEqual(r["forecast_liquid_in"], 2.4)
            self.assertEqual(r["liquid_error_pct"], 20)
            self.assertAlmostEqual(r["forecast_snow_in"]["kuchera"], 33.6)
            self.assertEqual(r["observed_slr_settled"], 7.0)


class TestResortFeed(unittest.TestCase):
    def test_parse_splits_mountains_and_handles_missing(self):
        from collectors.resort_scraper import ResortScraper
        feed = {
            "LastUpdate": "2026-11-23T22:33:40-0800", "OperatingStatus": "Open",
            "SnowReport": {
                "LastUpdate": "2026-11-23T06:48:56-0800", "BaseConditions": "Packed Powder", "Report": "<div>Line one<br>Line two</div>",
                "StormTotalIn": "45", "SeasonTotalIn": "71",
                "BaseArea": {"Name": "Palisades Base, el. 6200'", "BaseIn": "32", "Last24HoursIn": "0", "Last72HoursIn": "0", "Last7DaysIn": "44"},
                "MidMountainArea": {"Name": "Palisades Mid-Mountain, el. 8000'", "BaseIn": "46", "Last24HoursIn": "1", "Last72HoursIn": "2", "Last7DaysIn": "42"},
                "SummitArea": {"Name": "Palisades Siberia Crest, el. 8700'", "BaseIn": "--"},
                "Station4": {"Name": "Alpine Base, el. 6950'", "BaseIn": "35", "Last7DaysIn": "46"},
            },
            "CurrentConditions": {"Summit": {"Name": "Palisades Siberia Crest, el. 8700'", "TemperatureF": "31", "WindStrengthMph": 26, "WindGustsMph": 32}},
            "MountainAreas": [
                {"Name": "KT Peak", "OpenTrailsCount": 1, "TotalTrailsCount": 10, "Lifts": [{"Name": "KT-22 Express", "Status": "Open"}, {"Name": "Exhibition", "Status": "Closed"}]},
                {"Name": "Summit Peak", "OpenTrailsCount": 2, "TotalTrailsCount": 5, "Lifts": [{"Name": "Summit Express", "Status": "Scheduled"}]},
            ],
        }
        p = ResortScraper.parse(feed, "palisades_tahoe", "now")
        self.assertEqual(p["status"], "success")
        self.assertEqual(p["snow_areas"]["mid"]["elevation_ft"], 8000)
        self.assertEqual(p["snow_24h_inches"], 1.0)
        self.assertIsNone(p["snow_areas"]["summit"]["base_depth_in"])
        self.assertEqual((p["lifts_open"], p["lifts_total"]), (1, 2))
        self.assertEqual(p["report_text"], "Line one\nLine two")
        a = ResortScraper.parse(feed, "alpine_meadows", "now")
        self.assertEqual(a["snow_areas"]["base"]["new_7d_in"], 46.0)
        self.assertEqual((a["lifts_open"], a["lifts_total"]), (1, 1))


class TestNBM(unittest.TestCase):
    def test_unpack_bits(self):
        from collectors.grib2_simple import _unpack_bits
        # 3-bit values 1..6 packed big-endian: 001 010 011 100 101 110
        self.assertEqual(_unpack_bits(bytes([0b00101001, 0b11001011, 0b10000000]), 3, 6), [1, 2, 3, 4, 5, 6])

    def test_field_mapping(self):
        from collectors.nbm_client import NBMClient
        f = NBMClient._field
        self.assertEqual(f({"disc": 0, "cat": 0, "par": 0, "pdt": 0, "lev_type": 103, "lev_val": 2}), "tmp_k")
        self.assertEqual(f({"disc": 0, "cat": 1, "par": 29, "pdt": 8, "lev_type": 1, "lev_val": 0, "acc_len": 6}), "asnow_6h")
        self.assertEqual(f({"disc": 0, "cat": 19, "par": 236, "pdt": 0, "lev_type": 102, "lev_val": 0}), "snowlvl_m")
        self.assertIsNone(f({"disc": 0, "cat": 1, "par": 29, "pdt": 10, "lev_type": 1, "lev_val": 0}))

    def test_to_steps_spreads_six_hour_totals(self):
        from datetime import datetime, timezone
        from collectors.nbm_client import NBMClient
        rows = {str(h): {"tmp_k": 270.0, "dpt_k": 268.0, "apcp_1h": 0.0, "asnow_1h": 0.0, "slr": 12.0} for h in range(1, 49)}
        rows["54"] = {"tmp_k": 268.0, "dpt_k": 266.0, "apcp_6h": 6 * 2.54, "asnow_6h": 6 * 0.1 * 12 * 0.0254, "slr": 12.0}
        st = NBMClient.to_steps("2026-11-24T06:00:00+00:00", rows, 9000, datetime(2026, 11, 24, 7, tzinfo=timezone.utc))
        late = [x for x in st if x["lead_h"] in range(49, 55)]
        self.assertEqual(len(late), 6)
        self.assertAlmostEqual(late[0]["precip_in"], 0.1, places=3)
        self.assertAlmostEqual(late[0]["snowfall_rate_in_hr"], 1.2, places=2)
        self.assertTrue(late[0]["interpolated"])
