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


class TestNBMDownscale(unittest.TestCase):
    """Synthetic NBM box where temperature falls 3 F and 6 h snowfall rises 0.5 in per
    1,000 ft: the adjustment must recover those gradients at a target above its cell."""

    def _box(self):
        import math
        lats = [39.15 + 0.02 * j for j in range(5)]
        lons = [-120.30 + 0.025 * i for i in range(5)]
        ll, z = [], {}
        for a in lats:
            for b in lons:
                ll.append([round(a, 4), round(b, 4)])
                # terrain: a smooth hill, 6,000-8,600 ft
                elev = 6000 + 2600 * math.exp(-(((a - 39.19) / 0.03) ** 2 + ((b - (-120.25)) / 0.04) ** 2))
                z[f"{a:.4f},{b:.4f}"] = {"elevation_ft": round(elev)}
        rows = {}
        for fh in (1, 2, 3, 4, 5, 6):
            t_k, d_k, ap, asn, slr = [], [], [], [], []
            for a, b in ll:
                e = z[f"{a:.4f},{b:.4f}"]["elevation_ft"]
                tf = 40 - 3.0 * (e - 6000) / 1000
                t_k.append((tf - 32) * 5 / 9 + 273.15)
                d_k.append((tf - 8 - 32) * 5 / 9 + 273.15)
                ap.append(2.54)                                   # 0.1 in liquid per hour
                snow_in = max(0.0, (0.5 / 6) * (e - 6000) / 1000)  # snow grows with height
                asn.append(snow_in / 39.3701)
                slr.append(10.0)
            rows[str(fh)] = {"tmp_k": t_k, "dpt_k": d_k, "apcp_1h": ap, "asnow_1h": asn, "slr": slr,
                             "pop_1h": [90] * len(ll), "snowlvl_m": [1500] * len(ll)}
        return {"cycle_utc": "2026-11-24T00:00:00+00:00", "box": {"latlon": ll, "rows": rows}}, z

    def test_gradients_recovered(self):
        from datetime import datetime, timezone
        from collectors.nbm_client import NBMClient
        from collectors.nbm_downscale import Downscaler
        nbm, terrain = self._box()
        ds = Downscaler(nbm, terrain, NBMClient.to_steps)
        self.assertTrue(ds.ok)
        start = datetime(2026, 11, 24, 0, tzinfo=timezone.utc)
        steps, diag = ds.adjust(39.19, -120.25, 9000, start)
        self.assertEqual(len(steps), 6)
        dz = 9000 - diag["grid_elevation_ft"]
        cell_t = 40 - 3.0 * (diag["grid_elevation_ft"] - 6000) / 1000
        self.assertAlmostEqual(steps[0]["temp_f"], cell_t - 3.0 * dz / 1000, delta=0.3)
        self.assertAlmostEqual(diag["lapse_f_per_kft"]["median"], -3.0, delta=0.05)
        # 6 h snow at 9,000 ft from the synthetic rule: 0.5 in per 1,000 ft above 6,000 ft
        self.assertAlmostEqual(diag["snow_total_adjusted_in"], 1.5, delta=0.1)
        self.assertGreater(diag["snow_total_adjusted_in"], diag["snow_total_grid_in"])
        # liquid has no elevation dependence, so it must stay put
        self.assertAlmostEqual(diag["liquid_total_adjusted_in"], diag["liquid_total_grid_in"], delta=0.02)

    def test_regress_values(self):
        from collectors.nbm_client import NBMClient
        from collectors.nbm_downscale import Downscaler
        nbm, terrain = self._box()
        ds = Downscaler(nbm, terrain, NBMClient.to_steps)
        vals = {i: 2.0 + 1.0 * (ds.z[i] - 6000) / 1000 for i in range(len(ds.ll))}
        r = ds.regress_values(vals, 39.19, -120.25, 9000)
        self.assertAlmostEqual(r["value"], 5.0, delta=0.15)
        self.assertAlmostEqual(r["slope_per_kft"], 1.0, delta=0.05)


class TestCSSL(unittest.TestCase):
    """Snow Lab home page parsing: daily series from the embedded props, board reading from the text."""

    def _html(self):
        props = {"snowfallData": [{"dayIndex": 1, "date": "2026-10-01", "current": None},
                                  {"dayIndex": 2, "date": "2026-10-02", "current": 2.0},
                                  {"dayIndex": 3, "date": "2026-10-03", "current": 5.0}],
                 "precipitationData": [{"dayIndex": 1, "date": "2026-10-01", "current": 0.1},
                                       {"dayIndex": 2, "date": "2026-10-02", "current": 0.4},
                                       {"dayIndex": 3, "date": "2026-10-03", "current": 0.9}],
                 "sweData": [{"dayIndex": i, "date": f"10-0{i}", "current": 0.1 * i} for i in (1, 2, 3)]}
        chunk = json.dumps(json.dumps(props))   # page embeds the props as an escaped JS string
        return ("<html><body><span>Snowfall data last updated Oct 3, 8:11 AM PST</span>"
                "<div>24-Hour Snowfall</div><div>3 in</div><div>24-Hour Snowfall SWE</div><div>0.3 in</div>"
                "<div>7-Day Snowfall</div><div>5 in</div><div>Current Temperature</div><div>28.4°F</div>"
                f"<script>self.__next_f.push([1,{chunk}])</script></body></html>")

    def test_parse_home(self):
        from datetime import date
        from collectors.cssl_client import parse_home
        r = parse_home(self._html(), today=date(2026, 10, 3))
        self.assertEqual(r["water_year"], 2027)
        self.assertEqual([d["snow_new_in"] for d in r["daily"]], [None, 2.0, 3.0])
        self.assertEqual([d["precip_new_in"] for d in r["daily"]], [0.1, 0.3, 0.5])
        b = r["board"]
        self.assertEqual((b["snow_24h_in"], b["snow_24h_swe_in"], b["snow_7d_in"], b["temp_f"]), (3.0, 0.3, 5.0, 28.4))
        self.assertEqual(b["board_updated_pst"], "2026-10-03T08:11:00-08:00")

    def test_import_archive(self):
        """Dryad quirks: byte-order mark, an unnamed duplicate column, 'T' traces, '1,003' season totals, '--'."""
        import csv as csvmod
        import os
        import tempfile
        import zipfile
        from collectors.cssl_client import import_zip
        hdr = ("Date,Air Temp Max (C),Air Temp Min (C),24-hour Total Precip (mm),Season Total Precip (mm),"
               "% of Precip as Snow,% of Precip as Rain,New Snow (cm),Season Total Snow (cm),Snowpack depth (cm),"
               "Snow Water Equivalent (cm),Remarks")
        wy2021 = ("﻿" + hdr + ",\n"
                  "2020-11-09,2.0,-9.6,10,\"1,003\",100,0,24.5,24.5,24.375,2.0,--,24.5\n"
                  "2020-11-10,1.0,-8.0,T,\"1,003\",--,--,T,24.5,24,2.0,--,0\n")
        wy2025 = hdr + "\n2024-10-01,27,8,0,0,0,0,0,0,0,0,\n"
        with tempfile.TemporaryDirectory() as tmp:
            zp = os.path.join(tmp, "doi_10_6078_D1941T__v20251001.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("WY2021.csv", wy2021.encode("utf-8"))
                z.writestr("WY2025.csv", wy2025.encode("utf-8"))
                z.writestr("../README.md", "notes")
            r = import_zip(zp, os.path.join(tmp, "archive"))
            self.assertEqual(len(r["header_variants"]), 1)
            self.assertEqual(r["unnamed"], {"WY2021.csv": 1})
            self.assertTrue(os.path.exists(os.path.join(tmp, "archive", "v20251001", "README.md")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "README.md")))
            d = r["daily"]
            self.assertEqual((d["days"], d["water_years"], d["missing_water_years"]), (3, 2, [2022, 2023, 2024]))
            self.assertEqual(d["unparsed_values"], {})
            with open(d["file"]) as fh:
                rows = list(csvmod.DictReader(fh))
        first, trace, wy25 = rows
        self.assertEqual((first["water_year"], first["season_precip_mm"], first["new_snow_cm"], first["remarks"]),
                         ("2021", "1003", "24.5", ""))
        self.assertEqual((trace["precip_mm"], trace["precip_trace"], trace["new_snow_cm"], trace["new_snow_trace"],
                          trace["precip_snow_pct"]), ("0", "1", "0", "1", ""))
        self.assertEqual((wy25["water_year"], wy25["tmax_c"]), ("2025", "27"))


class TestNRCS(unittest.TestCase):
    """SNOTEL hourly: payload parsing, water-year files filled to every hour, incremental merge."""

    @staticmethod
    def _payload(triplet, values):
        """values: {element: [(date, value, qc, qa)]}"""
        return [{"stationTriplet": triplet, "data": [
            {"stationElement": {"elementCode": el},
             "values": [dict({"date": d, "value": v, "qcFlag": qc}, **({"qaFlag": qa} if qa else {}))
                        for d, v, qc, qa in rows]} for el, rows in values.items()]}]

    def test_parse_values(self):
        from collectors.nrcs_client import parse_values
        p = self._payload("784:CA:SNTL", {"WTEQ": [("2021-10-01 00:00", 1.0, "V", "A")],
                                          "TOBS": [("2021-10-01 00:00", 21.9, "C", None)],
                                          "PREC": [("2021-10-01 00:00", None, "S", "R")],
                                          "XXXX": [("2021-10-01 00:00", 5, "V", None)]})
        cell = parse_values(p)["784:CA:SNTL"]["2021-10-01 00:00"]
        self.assertEqual((cell["wteq_in"], cell["wteq_qc"], cell["wteq_qa"]), ("1", "V", "A"))
        self.assertEqual((cell["tobs_f"], cell["tobs_qc"], cell["tobs_qa"]), ("21.9", "C", ""))
        self.assertEqual((cell["prec_in"], cell["prec_qc"]), ("", "S"))
        self.assertNotIn("xxxx", " ".join(cell))

    def test_water_year_files_and_merge(self):
        import csv as csvmod
        import tempfile
        from datetime import datetime
        from collectors.nrcs_client import apply_values, parse_values, read_csv
        until = datetime(2021, 10, 1, 2, 0)
        p = self._payload("784:CA:SNTL", {"WTEQ": [("2021-09-30 23:00", 0.0, "V", "A"), ("2021-10-01 01:00", 0.1, "V", None)],
                                          "TOBS": [("2021-10-01 01:00", 30.5, "C", None)]})
        with tempfile.TemporaryDirectory() as tmp:
            changed = apply_values(tmp, parse_values(p), until)
            self.assertEqual(changed, {"SQV": {2021: 1, 2022: 1}})
            wy21 = read_csv(Path(tmp) / "SQV" / "WY2021.csv")
            self.assertEqual(len(wy21), 8760)                       # every hour of WY2021, blanks included
            self.assertEqual(wy21["2021-09-30 23:00"]["wteq_in"], "0")
            self.assertEqual(wy21["2020-10-01 00:00"]["wteq_in"], "")
            with open(Path(tmp) / "SQV" / "WY2022.csv") as f:
                rows = list(csvmod.DictReader(f))
            self.assertEqual([r["time_pst"] for r in rows], ["2021-10-01 00:00", "2021-10-01 01:00", "2021-10-01 02:00"])
            self.assertEqual(rows[1]["time_utc"], "2021-10-01T09:00Z")
            # an NRCS edit to one element keeps the other elements of that hour
            edit = self._payload("784:CA:SNTL", {"WTEQ": [("2021-10-01 01:00", 0.2, "E", "P")]})
            apply_values(tmp, parse_values(edit), until)
            r = read_csv(Path(tmp) / "SQV" / "WY2022.csv")["2021-10-01 01:00"]
            self.assertEqual((r["wteq_in"], r["wteq_qc"], r["wteq_qa"], r["tobs_f"]), ("0.2", "E", "P", "30.5"))

    def test_update_uses_changed_since(self):
        import tempfile
        from datetime import datetime
        from unittest import mock
        from collectors import nrcs_client as n
        calls = []

        def fake_fetch(triplets, begin, end, changed_since=None):
            calls.append((len(triplets), begin, end, changed_since))
            return self._payload("848:CA:SNTL", {"SNWD": [("2026-11-24 09:00", 32, "V", None)]})

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "state.json").write_text(json.dumps({"first_wy": 2027, "last_sync_pst": "2026-11-24 08:00"}))
            with mock.patch.object(n, "fetch", fake_fetch), \
                    mock.patch.object(n, "now_pst", lambda: datetime(2026, 11, 24, 10, 0)):
                r = n.update(tmp)
            self.assertEqual(calls, [(7, datetime(2026, 10, 1), datetime(2026, 11, 24, 10, 0), datetime(2026, 11, 23, 8, 0))])
            self.assertEqual(r["changed"], {"WC3": 1})
            self.assertEqual(n.read_csv(Path(tmp) / "WC3" / "WY2027.csv")["2026-11-24 09:00"]["snwd_in"], "32")
            self.assertEqual(len(n.read_csv(Path(tmp) / "SQV" / "WY2027.csv")), 55 * 24 - 13)   # Oct 1 00:00 .. Nov 24 10:00
            self.assertEqual(json.loads((Path(tmp) / "state.json").read_text())["last_sync_pst"], "2026-11-24 10:00")


def _bits_writer():
    """Tiny MSB-first bit writer for building GRIB2 test messages."""
    state = {"v": 0, "n": 0}

    def put(value, width):
        if width:
            state["v"] = (state["v"] << width) | (value & ((1 << width) - 1))
            state["n"] += width

    def pad():
        r = (-state["n"]) % 8
        put(0, r)

    def data():
        pad()
        return state["v"].to_bytes(state["n"] // 8, "big") if state["n"] else b""
    return put, pad, data


def _pack_complex(ints, order=2, group_len=7, missing=(), tmpl=3, D=1):
    """Encode integers as GRIB2 sections 5 and 7 (template 5.2/5.3). `missing`: storage positions."""
    import struct
    miss = set(missing)
    seq = [x for k, x in enumerate(ints) if k not in miss]
    if tmpl == 3:
        d = [0] * min(order, len(seq))
        for n in range(order, len(seq)):
            d.append(seq[n] - seq[n - 1] if order == 1 else seq[n] - 2 * seq[n - 1] + seq[n - 2])
        minsd = min(d[order:]) if len(d) > order else 0
        packed_seq = [0] * min(order, len(seq)) + [x - minsd for x in d[order:]]
    else:
        minsd, packed_seq = 0, list(seq)
    it = iter(packed_seq)
    full = [None if k in miss else next(it) for k in range(len(ints))]   # None = missing
    groups = [full[k:k + group_len] for k in range(0, len(full), group_len)]
    nbits = 12
    refs, widths, vals = [], [], []
    for g in groups:
        real = [x for x in g if x is not None]
        if not real:
            refs.append((1 << nbits) - 1); widths.append(0); vals.append([]); continue
        ref = min(real)
        span = max(real) - ref + (1 if miss else 0)    # with missing values on, all-ones is reserved in every group
        w = span.bit_length()
        refs.append(ref); widths.append(w)
        vals.append([((1 << w) - 1) if x is None else x - ref for x in g])
    put, pad, data = _bits_writer()
    nb_extra = 2
    if tmpl == 3:
        for v in ([seq[0], seq[1]] if order == 2 else [seq[0]]) + [minsd]:
            put((1 << 15) | -v if v < 0 else v, nb_extra * 8)
    for r in refs:
        put(r, nbits)
    pad()
    bw = max(widths).bit_length()
    for w in widths:
        put(w, bw)
    pad()
    for w, v in zip(widths, vals):
        for x in v:
            put(x, w)
    body = data()
    sm16 = lambda v: (0x8000 | -v) if v < 0 else v
    s5 = struct.pack(">IBIH", 0, 5, len(ints), tmpl) + struct.pack(">fHH", 0.0, sm16(0), sm16(D))
    s5 += bytes([nbits, 1, 1, 1 if miss else 0]) + struct.pack(">ff", 9999.0, 0.0)
    s5 += struct.pack(">IBBIBIB", len(groups), 0, bw, group_len, 1, len(groups[-1]), 0)
    if tmpl == 3:
        s5 += bytes([order, nb_extra])
    s5 = struct.pack(">I", len(s5)) + s5[4:]
    s7 = struct.pack(">IB", 5 + len(body), 7) + body
    return s5, s7


class TestGrib2Complex(unittest.TestCase):
    """Complex packing decoder: spatial differencing order 1/2, missing values, early stop, row order."""

    def _field(self, n=500):
        import math
        return [int(500 + 300 * math.sin(k / 9.0) + (k % 13) * 3 + (40 if k % 97 == 0 else 0)) for k in range(n)]

    def test_order2_with_missing_and_stop(self):
        from collectors.grib2_complex import decode
        ints = self._field()
        ints[100:120] = [0] * 20                       # a constant run -> zero-width groups
        missing = {5, 6, 7, 250} | set(range(301, 315))   # includes one fully missing group
        s5, s7 = _pack_complex(ints, order=2, missing=missing)
        got = decode(s5, s7)
        want = [None if k in missing else x / 10 for k, x in enumerate(ints)]
        self.assertEqual(len(got), len(ints))
        for a, b in zip(got, want):
            self.assertTrue((a is None and b is None) or abs(a - b) < 1e-9, (a, b))
        part = decode(s5, s7, stop=260)
        self.assertEqual(len(part), 260)
        self.assertEqual(part, got[:260])

    def test_order1_and_template_52(self):
        from collectors.grib2_complex import decode
        ints = self._field(300)
        for tmpl, order in ((3, 1), (2, 0)):
            s5, s7 = _pack_complex(ints, order=order, tmpl=tmpl)
            self.assertEqual([round(v * 10) for v in decode(s5, s7)], ints)

    def test_storage_index_boustrophedon(self):
        from collectors.grib2_complex import storage_index
        self.assertEqual(storage_index(0, 0, 5, 0x50), 0)
        self.assertEqual(storage_index(0, 1, 5, 0x50), 9)    # odd rows run right to left
        self.assertEqual(storage_index(4, 1, 5, 0x50), 5)
        self.assertEqual(storage_index(0, 1, 5, 0x40), 5)


class TestNBMArchive(unittest.TestCase):
    """Index parsing, grid geometry, storm-day leads, partial downloads."""

    GRID = {"tmpl": 30, "radius": 6371200.0, "nx": 2345, "ny": 1597, "la1": 19.229, "lo1": -126.2766, "lad": 25.0,
            "lov": -95.0, "dx": 2539.703, "dy": 2539.703, "scan": 0x50, "latin1": 25.0, "latin2": 25.0}

    def test_parse_idx(self):
        from collectors.nbm_archive import parse_idx
        idx = ("1:0:d=2024120112:APCP:surface:23-24 hour acc fcst:\n"
               "2:1000:d=2024120112:APCP:surface:18-24 hour acc fcst:\n"
               "3:2500:d=2024120112:APCP:surface:18-24 hour acc fcst:prob >0.254:prob fcst 255/255\n"
               "4:3000:d=2024120112:TMP:2 m above ground:24 hour fcst:\n"
               "5:4200:d=2024120112:TMP:2 m above ground:24 hour fcst:ens std dev\n"
               "6:5000:d=2024120112:var discipline=0 center=7 local_table=1 parmcat=1 parm=233:surface:24 hour fcst:\n"
               "7:6000:d=2024120112:ASNOW:surface:18-24 hour acc fcst:\n")
        got = parse_idx(idx, 24)
        self.assertEqual(got["apcp_6h"], (1000, 2499))
        self.assertEqual(got["apcp_1h"], (0, 999))
        self.assertEqual(got["tmp_k"], (3000, 4199))
        self.assertEqual(got["slr"], (5000, 5999))
        self.assertEqual(got["asnow_6h"], (6000, None))
        self.assertNotIn("tmp_k", parse_idx(idx, 18))

    def test_geometry_and_layout(self):
        from collectors import nbm_archive as na
        i, j = na.grid_ij(self.GRID, 39.19, -120.27)
        la, lo = na.cell_latlon(self.GRID, round(i), round(j))
        self.assertLess(abs(la - 39.19), 0.02)
        self.assertLess(abs(lo + 120.27), 0.02)
        lay = na.box_layout(self.GRID, na.EXT_BOX, live_latlons=[(la, lo)])
        self.assertEqual(len(lay["latlon"]), lay["nx"] * lay["ny"])
        self.assertLess(lay["latlon"][0][0], lay["latlon"][-1][0])              # south to north
        self.assertLess(lay["latlon"][0][1], lay["latlon"][lay["nx"] - 1][1])   # west to east
        self.assertEqual(lay["latlon"][lay["live_cells"][0]], [la, lo])
        self.assertEqual(lay["stop"], max(lay["storage"]) + 1)

    def test_lead_files(self):
        from datetime import datetime, timezone
        from collectors.nbm_archive import lead_files
        self.assertEqual(lead_files("2026-11-18", 1), (datetime(2026, 11, 18, 12, tzinfo=timezone.utc), [6, 12, 18, 24]))
        self.assertEqual(lead_files("2026-11-18", 2), (datetime(2026, 11, 17, 12, tzinfo=timezone.utc), [30, 36, 42, 48]))

    def test_partial_download_matches_full(self):
        import struct
        from unittest import mock
        from collectors import nbm_archive as na
        from collectors.grib2_complex import decode, sections
        ints = [int(1000 + 400 * ((k * 37) % 101) / 101 + (k % 7)) for k in range(40000)]
        s5, s7 = _pack_complex(ints, order=2, group_len=25)
        s3 = bytearray(81); s3[0:4] = struct.pack(">I", 81); s3[4] = 3; s3[12:14] = struct.pack(">H", 30)
        s4 = bytearray(34); s4[0:4] = struct.pack(">I", 34); s4[4] = 4; s4[7:9] = struct.pack(">H", 0)
        s4[9], s4[10], s4[17], s4[22], s4[23] = 0, 0, 1, 103, 0; s4[24:28] = struct.pack(">I", 2)
        s1 = struct.pack(">IB", 21, 1) + bytes(16)
        s6 = struct.pack(">IBB", 6, 6, 255)
        body = s1 + bytes(s3) + bytes(s4) + s5 + s6 + s7 + b"7777"
        msg = b"GRIB" + bytes([0, 0, 0, 2]) + struct.pack(">Q", 16 + len(body)) + body
        served = []

        def fake_request(url, rng=None, **kw):
            a, b = rng
            chunk = msg[a:(len(msg) if b is None else b + 1)]
            served.append(len(chunk))
            return chunk

        stop = 15000
        reader = na.ArchiveReader()
        reader.layout = lambda grid: {"stop": stop, "storage": list(range(stop))}
        with mock.patch.object(na, "_request", fake_request), mock.patch.object(na, "HEAD_MIN", 1024):
            part, _, nbytes = reader.fetch_message("u", (0, len(msg) - 1))
        sec = sections(part)
        self.assertEqual([round(v * 10) for v in decode(sec[5], sec[7], stop=stop)], ints[:stop])
        self.assertLess(nbytes, 0.6 * len(msg))
        self.assertEqual(sum(served), nbytes)


class TestStormDays(unittest.TestCase):
    """SNOTEL storm-days: 04:00 PST medians, suspect and midnight values ignored, confirmation."""

    def test_storm_day(self):
        import tempfile
        from datetime import date, datetime, timedelta
        from collectors.nrcs_client import write_csv
        from collectors.storm_days import storm_days
        with tempfile.TemporaryDirectory() as tmp:
            for code, gain, gauge in (("SQV", 1.0, 0.5), ("WC3", 0.1, 0.1), ("TCC", 0.0, 0.0)):
                rows = {}
                t = datetime(2026, 11, 17, 0)
                while t < datetime(2026, 11, 20, 0):
                    k = t.strftime("%Y-%m-%d %H:%M")
                    storm = min(1.0, max(0.0, (t - datetime(2026, 11, 18, 8)).total_seconds() / 14400))   # 08:00-12:00 PST
                    rows[k] = {"wteq_in": f"{5 + gain * storm:.2f}", "wteq_qc": "V", "prec_in": f"{3 + gauge * storm:.2f}",
                               "prec_qc": "V", "snwd_in": f"{30 + 10 * gain * storm:.0f}", "snwd_qc": "V", "tobs_f": "25", "tobs_qc": "C"}
                    t += timedelta(hours=1)
                rows["2026-11-18 03:00"]["wteq_in"], rows["2026-11-18 03:00"]["wteq_qc"] = "206", "S"     # suspect spike
                rows["2026-11-19 00:00"]["wteq_in"], rows["2026-11-19 00:00"]["wteq_qc"] = "9.9", "E"     # edited midnight
                write_csv(f"{tmp}/{code}/WY2027.csv", rows, 2027, datetime(2026, 11, 19, 23))
            days = storm_days(tmp, report_sites=["SQV", "WC3", "TCC"], first=date(2026, 11, 17), last=date(2026, 11, 18))
        self.assertEqual([d["date"] for d in days], ["2026-11-18"])
        d = days[0]
        self.assertEqual(d["triggered_by"], ["SQV"])
        self.assertEqual(d["obs"]["SQV"]["swe_gain_in"], 1.0)
        self.assertTrue(d["confirmed"])
        self.assertEqual(d["confirmed_by"], "gauge")
        self.assertEqual(d["obs"]["TCC"]["swe_gain_in"], 0.0)

    def test_anchor_drops_suspect(self):
        from datetime import date
        from collectors.storm_days import anchor
        vals = {2: ("5.0", "V"), 3: ("206", "S"), 4: ("5.1", "V"), 5: ("206", "S"), 6: ("5.2", "E")}
        rows = {f"2026-11-18 {h:02d}:00": {"time_pst": f"2026-11-18 {h:02d}:00", "wteq_in": v, "wteq_qc": q}
                for h, (v, q) in vals.items()}
        self.assertEqual(anchor(rows, date(2026, 11, 18), "wteq_in"), 5.1)   # 5.2 if the suspect values were kept
        rows["2026-11-18 04:00"]["wteq_qc"] = "S"
        self.assertIsNone(anchor(rows, date(2026, 11, 18), "wteq_in"))        # fewer than 3 usable hours


class TestElevationMethods(unittest.TestCase):
    """Nov 24, 2026 changes: NBM uses the fitted line at the tier height (no anchor cell);
    Open-Meteo models move the raw grid cell along the model's own column."""

    def test_nbm_anchor_cell_anomaly_not_carried(self):
        from datetime import datetime, timezone
        from collectors.nbm_client import NBMClient
        from collectors.nbm_downscale import Downscaler
        nbm, terrain = TestNBMDownscale()._box()
        ds = Downscaler(nbm, terrain, NBMClient.to_steps)
        start = datetime(2026, 11, 24, 0, tzinfo=timezone.utc)
        _, diag = ds.adjust(39.19, -120.25, 9000, start)
        g = next(i for i, (a, b) in enumerate(ds.ll) if a == diag["grid_lat"] and b == diag["grid_lon"])
        for r in nbm["box"]["rows"].values():           # make the nearest cell 6 F colder than its neighbors
            r["tmp_k"][g] -= 6 * 5 / 9
        ds2 = Downscaler(nbm, terrain, NBMClient.to_steps)
        steps, _ = ds2.adjust(39.19, -120.25, 9000, start)
        # the old anchor method carried the full 6 F; the fitted line shares it with the neighbors
        line = 40 - 3.0 * 3.0
        self.assertLess(line - steps[0]["temp_f"], 6.0 - 1.0)
        self.assertGreater(line - steps[0]["temp_f"], 0.0)

    def _profile(self, inversion):
        # column at 2,000-3,500 m; with an inversion, 2,000 -> 2,600 m warms by 4 C
        levels = []
        for p, z in ((800, 2000), (775, 2300), (750, 2600), (700, 3100), (650, 3600)):
            t = (-2.0 + 4.0 * (z - 2000) / 600 if z <= 2600 else 2.0 - 6.5 * (z - 2600) / 1000) if inversion else -2.0 - 6.5 * (z - 2000) / 1000
            levels.append({"p": p, "z": z, "t": t, "rh": 60.0, "rhi": 65.0, "tw": t - 3, "td": t - 6, "w": 0.0, "ws": 10.0, "wd": 250.0})
        return [{"_levels": levels, "wet_bulb_zero_ft": 9000, "freezing_level_ft": 9000, "snow_level_ft": 8500}]

    def test_open_meteo_column_shift(self):
        from collectors.open_meteo_client import OpenMeteoClient, _height_at_pressure
        prof = self._profile(True)
        self.assertAlmostEqual(_height_at_pressure(prof[0]["_levels"], 787.5), 2150, delta=15)
        cell_f = 25.0
        hourly = {"time": ["2026-11-24T09:00"], "temperature_2m": [cell_f], "dew_point_2m": [15.0], "relative_humidity_2m": [65],
                  "precipitation": [0.0], "snowfall": [0.0], "precipitation_probability": [0], "surface_pressure": [800.0],
                  "wind_speed_10m": [5.0], "wind_gusts_10m": [9.0], "wind_direction_10m": [250.0], "cloud_cover": [0], "visibility": [20000]}
        c = OpenMeteoClient()
        inv = c._build_tier({"hourly": hourly}, prof, "Summit", 2600)["_steps"][0]
        self.assertEqual(inv["cell_elevation_ft"], round(2000 * 3.28084))
        self.assertAlmostEqual(inv["temp_shift_f"], 4.0 * 1.8, delta=0.05)       # column warms 4 C from cell to tier
        self.assertAlmostEqual(inv["temp_f"], cell_f + 7.2, delta=0.1)
        self.assertAlmostEqual(inv["fixed_lapse_shift_f"], -6.5 * 0.6 * 1.8, delta=0.05)   # what Open-Meteo would do
        std = c._build_tier({"hourly": hourly}, self._profile(False), "Summit", 2600)["_steps"][0]
        self.assertAlmostEqual(std["temp_f"], cell_f - 6.5 * 0.6 * 1.8, delta=0.1)
        self.assertLessEqual(inv["dew_point_f"], inv["temp_f"])


class TestColumnGroundAndRoads(unittest.TestCase):
    """Nov 24, 2026: freezing level from the highest crossing (no below-ground dips), free air only above the
    model's ground, and Nevada roads shown as having no live feed instead of defaulting to open."""

    def _upper(self, p_sfc):
        # 800 hPa is below the model's ground and carries the cold surface temperature extrapolated downward
        lv = {1000: (100, 13.0), 850: (1570, 2.2), 800: (2064, -0.5), 750: (2592, 6.2), 700: (3154, 3.9), 650: (3753, 1.3),
              600: (4391, -2.9), 550: (5073, -7.0), 500: (5806, -12.5), 450: (6600, -18.5), 400: (7460, -25.0)}
        h = {"time": ["2026-11-26T12:00"], "surface_pressure": [p_sfc]}
        for p, (z, t) in lv.items():
            h[f"geopotential_height_{p}hPa"] = [z]; h[f"temperature_{p}hPa"] = [t]; h[f"relative_humidity_{p}hPa"] = [80.0]
            h[f"vertical_velocity_{p}hPa"] = [0.0]; h[f"wind_speed_{p}hPa"] = [20.0]; h[f"wind_direction_{p}hPa"] = [250.0]
        return {"hourly": h}

    def test_freezing_level_ignores_below_ground_crossing(self):
        from collectors.open_meteo_client import OpenMeteoClient, _highest_crossing
        self.assertAlmostEqual(_highest_crossing([0, 1, 2, 3], [1, -1, 1, -1], 0.0), 2.5)
        prof = OpenMeteoClient()._build_vertical_profile(self._upper(761.0))[0]
        self.assertGreater(prof["freezing_level_ft"], 12000)          # top of the warm layer, not ~6,500 ft
        self.assertFalse(prof["freezing_level_below_ground"])
        self.assertAlmostEqual(prof["ground_ft"], 2440 * 3.28084, delta=250)
        self.assertIsNotNone(prof["dgz_base_ft"])

    def test_free_air_blank_below_model_ground(self):
        from collectors.open_meteo_client import OpenMeteoClient
        c = OpenMeteoClient()
        prof = c._build_vertical_profile(self._upper(761.0))
        hourly = {"time": ["2026-11-26T12:00"], "temperature_2m": [30.0], "dew_point_2m": [20.0], "relative_humidity_2m": [65],
                  "precipitation": [0.0], "snowfall": [0.0], "precipitation_probability": [0], "surface_pressure": [800.0],
                  "wind_speed_10m": [5.0], "wind_gusts_10m": [9.0], "wind_direction_10m": [250.0], "cloud_cover": [0], "visibility": [20000]}
        base = c._build_tier({"hourly": hourly}, prof, "Base", 1890)["_steps"][0]
        summit = c._build_tier({"hourly": hourly}, prof, "Summit", 2758)["_steps"][0]
        self.assertIsNone(base["free_air_temp_f"])
        self.assertIsNotNone(summit["free_air_temp_f"])

    def test_roads_without_feed(self):
        from unittest import mock
        from collectors.caltrans_client import CaltransClient
        line = [[39.0 + i * 0.001, -119.95] for i in range(100)]
        roads = [{"id": "nv", "route": "NV 28", "name": "NV", "feed": "none", "feed_note": "no feed", "polyline": line},
                 {"id": "us", "route": "50", "name": "US", "feed": "partial", "feed_note": "part", "polyline": line},
                 {"id": "ca", "route": "89", "name": "CA", "polyline": line}]
        rec = {"route": "50", "lat": 39.05, "lon": -119.95, "ccStatus": {"status": "R-2", "description": "chains"}, "locationName": "x"}
        c = CaltransClient()
        with mock.patch.object(c, "fetch_district_chain_controls", lambda district=3: []):
            seg = {s["id"]: s for s in c.get_road_conditions(roads)["segments"]}
        self.assertEqual((seg["nv"]["status"], seg["us"]["status"], seg["ca"]["status"]), ("NO FEED", "NO FEED", "R-0"))
        with mock.patch.object(c, "fetch_district_chain_controls", lambda district=3: [rec] if district == 3 else []):
            seg = {s["id"]: s for s in c.get_road_conditions(roads)["segments"]}
        self.assertEqual(seg["us"]["status"], "R-2")
        self.assertIn("California part only", seg["us"]["checkpoint"])
        self.assertEqual(seg["nv"]["status"], "NO FEED")


class TestBlend(unittest.TestCase):
    """Static model blend: weighted hourly mean, increments for totals, stop rule, SLR consistency, spread."""

    @staticmethod
    def _member(n, snow, liq, temp, wdir, frac=1.0):
        out, cum, k = [], 0.0, 0.0
        for i in range(n):
            cum += snow
            k += snow * 1.5
            out.append({"time": f"2026-11-24T{i:02d}:00Z", "precip_in": liq, "snowfall_rate_in_hr": snow, "model_snowfall_in_hr": liq * 7,
                        "cumulative_snow_inches": cum, "kuchera_cumulative_inches": k, "experimental_cumulative_inches": cum,
                        "slr": snow / (liq * frac) if liq else 10, "snow_fraction": frac, "precip_probability": 90, "temp_f": temp,
                        "dew_point_f": temp - 4, "wind_mph": 20.0, "wind_dir_deg": wdir, "precip_phase": "snow"})
        return out

    def test_blend_steps(self):
        from collectors.open_meteo_client import OpenMeteoClient
        a = self._member(6, 1.0, 0.10, 20.0, 350)     # 10:1
        b = self._member(4, 2.0, 0.10, 30.0, 10)      # 20:1, ends after 4 hours
        c = self._member(2, 0.0, 0.00, 25.0, 0)       # ends after 2 hours
        steps = OpenMeteoClient._blend_steps({"a": a, "b": b, "c": c}, {"a": 1, "b": 1, "c": 1}, 1.5)
        self.assertEqual(len(steps), 4)                         # hour 5 has only "a" (weight 1 < 1.5): stop
        h0, h3 = steps[0], steps[3]
        self.assertAlmostEqual(h0["snowfall_rate_in_hr"], 1.0, places=2)    # (1 + 2 + 0) / 3
        self.assertAlmostEqual(h3["snowfall_rate_in_hr"], 1.5, places=2)    # c gone: (1 + 2) / 2
        self.assertAlmostEqual(h3["cumulative_snow_inches"], 1.0 + 1.0 + 1.5 + 1.5, places=2)   # no jump when c ends
        self.assertAlmostEqual(h3["kuchera_cumulative_inches"], 1.5 * (1.0 + 1.0 + 1.5 + 1.5), places=2)
        self.assertAlmostEqual(h3["slr"], 15.0, places=1)       # blended snow / blended liquid: 1.5 / 0.1
        self.assertEqual(h0["temp_f"], 25.0)
        self.assertTrue(h0["wind_dir_deg"] in (0, 360) or h0["wind_dir_deg"] <= 1)   # 350 and 10 average to north
        self.assertEqual((h3["members"], h3["member_cum_snow_min"], h3["member_cum_snow_max"]), (2, 4.0, 8.0))
        self.assertEqual(h3["precip_phase"], "snow")

    def test_lead_weights(self):
        from collectors.open_meteo_client import OpenMeteoClient
        a = self._member(4, 1.0, 0.10, 20.0, 270)
        b = self._member(4, 3.0, 0.10, 30.0, 270)
        steps = OpenMeteoClient._blend_steps({"a": a, "b": b}, {"a": 1, "b": 1}, 1.0, {"b": [[0, 3], [1, 3], [3, 1]]})
        self.assertAlmostEqual(steps[0]["snowfall_rate_in_hr"], 2.5, places=2)        # (1 + 3*3) / 4
        self.assertAlmostEqual(steps[2]["snowfall_rate_in_hr"], 7 / 3, places=2)      # b weight 2 at hour 2
        self.assertAlmostEqual(steps[3]["snowfall_rate_in_hr"], 2.0, places=2)        # equal weights by hour 3
        self.assertEqual(OpenMeteoClient._lead_weight([[0, 5], [18, 5], [48, 1]], 33), 3.0)


class TestBlendWeights(unittest.TestCase):
    """Skill weights: archived model liquid vs SNOTEL snow-water gain over cold 24 h windows."""

    def test_pairs_and_weights(self):
        import blend_weights as bw
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
        rows = {}
        for h in range(-3, 52):
            t = (start + timedelta(hours=h)).astimezone(bw.PST)
            swe = 5.0 + min(1.0, max(0.0, h / 24.0))                 # +1.0 in over the first 24 h, then flat
            rows[t.strftime("%Y-%m-%d %H:%M")] = {"wteq_in": f"{swe:.2f}", "wteq_qc": "V", "tobs_f": "25", "tobs_qc": "C"}
        snap = {"resorts": {"palisades_tahoe": {
            "good": {"tiers": {"mid": {"start": "2026-11-24T12:00Z", "precip_in": [0.045] * 72}}},
            "wet": {"tiers": {"mid": {"start": "2026-11-24T12:00Z", "precip_in": [0.1] * 72}}},
            "blend": {"tiers": {"mid": {"start": "2026-11-24T12:00Z", "precip_in": [0.04] * 72}}}}}}
        pr = bw.pairs([snap], rows)
        f, o = pr[("good", "day 1")][0]
        self.assertAlmostEqual(f, 1.08, places=2)
        self.assertAlmostEqual(o, 1.0, places=1)
        res = bw.suggest(pr, min_n=1)["day 1"]
        self.assertNotIn("blend", res)                                   # blends are not scored as members
        self.assertGreater(res["good"]["weight"], res["wet"]["weight"])  # lower MAE -> higher weight
        self.assertAlmostEqual((res["good"]["weight"] + res["wet"]["weight"]) / 2, 1.0, places=2)

    def test_hindcast_pairs(self):
        import blend_weights as bw
        from datetime import date, datetime, timedelta, timezone
        start = datetime(2025, 2, 13, 12, tzinfo=timezone.utc)
        rows = {}
        for h in range(-3, 28):
            t = (start + timedelta(hours=h)).astimezone(bw.PST)
            rows[t.strftime("%Y-%m-%d %H:%M")] = {"wteq_in": f"{10 + min(1.5, max(0.0, h / 16)):.2f}", "wteq_qc": "V", "tobs_f": "24", "tobs_qc": "C"}
        series = {"m": {(start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M"): 0.05 for k in range(0, 26)}}
        pr = bw.hindcast_pairs(series, rows, [date(2025, 2, 13)])
        day, f, o = pr["m"][0]
        self.assertAlmostEqual(f, 1.2, places=2)        # 13Z..12Z: 24 hourly values
        self.assertAlmostEqual(o, 1.5, places=1)
        s = bw.score({"m": pr["m"], "n": [(day, 1.5, 1.5)]}, min_n=1)
        self.assertGreater(s["n"]["weight"] if s["n"]["mae"] > 0 else 9, 0)
        self.assertIsNotNone(s["m"]["weight"])


class TestCalibrationBaseline(unittest.TestCase):
    """The scoring script's estimate: raw = nearest cell, adjusted = the fitted line at the point."""

    def test_estimate(self):
        import calibration_baseline as cb
        nbm, terrain = TestNBMDownscale()._box()
        box = cb.Box(nbm["box"], terrain)
        vals = [40 - 3.0 * (z - 6000) / 1000 for z in box.z]        # temperature falling 3 F per 1,000 ft
        raw, adj = box.estimate(vals, 39.19, -120.25, 9000, cross=False, lapse_clamp=True)
        self.assertAlmostEqual(adj, 40 - 9.0, delta=0.05)
        self.assertNotAlmostEqual(raw, adj, delta=0.5)                 # the nearest cell sits lower than 9,000 ft


class TestBlendWeightsLongLead(unittest.TestCase):
    """--lead-day uses the Previous Runs API variable; --apply writes weights into the config."""

    def test_lead_day_fetch_and_apply(self):
        import io
        import tempfile
        from unittest import mock
        import blend_weights as bw
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=0):
            seen["url"] = req.full_url
            return Resp(json.dumps({"hourly": {"time": ["2026-02-17T13:00"], "precipitation_previous_day3": [0.2]}}).encode())

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(bw, "HINDCAST_DIR", Path(tmp) / "hc"), mock.patch("urllib.request.urlopen", fake_urlopen):
                out = bw.fetch_hindcast("gem_seamless", "SQV", 39.19, -120.27, "2025-11-01", "2026-04-30", lead_day=3)
            self.assertEqual(out, {"2026-02-17T13:00": 0.2})
            self.assertIn("previous-runs-api", seen["url"])
            self.assertIn("precipitation_previous_day3", seen["url"])
            self.assertTrue((Path(tmp) / "hc" / "gem_seamless_SQV_2025-11-01_2026-04-30_d3.json").exists())
            cfg = Path(tmp) / "config"; cfg.mkdir()
            (cfg / "sources.json").write_text(json.dumps({"sources": [], "blends": [{"id": "blend", "label": "Equal blend", "members": {"a": 1}}]}))
            with mock.patch.object(bw, "BASE_DIR", Path(tmp)):
                bw.apply_weights("blend_skill_long", {"icon": {"weight": 1.2, "mae": 0.4}, "gem": {"weight": 0.8, "mae": 0.6}, "ukmo": {"weight": None, "mae": 0.9}},
                                 {"created": "2026-11-24T00:00:00", "lead": "day-3 lead", "period": "2025-11-01 to 2026-11-24", "site_days": 40})
            d = json.loads((cfg / "sources.json").read_text())
        b = next(x for x in d["blends"] if x["id"] == "blend_skill_long")
        self.assertEqual(b["members"], {"icon": 1.2, "gem": 0.8})       # members without enough windows are left out
        self.assertEqual(b["label"], "Long-lead skill blend (beta)")
        self.assertEqual(b["fitted"]["site_days"], 40)


class TestPrecipCorrection(unittest.TestCase):
    """Shared elevation shift: linear weights, lake cells, running-total clip, live correction, corrected blend."""

    @staticmethod
    def _cells(lat0, lon0, field):
        from collectors.nbm_downscale import _xy, _cross
        xc0 = _cross(*_xy(lat0, lon0))
        out = []
        for di, dj, z in [(0, 0, 7500), (1, 0, 7800), (-1, 0, 7000), (0, 1, 6800), (0, -1, 8100), (1, 1, 7300), (-1, -1, 6400)]:
            la, lo = lat0 + di * 0.03, lon0 + dj * 0.04
            out.append({"lat": la, "lon": lo, "z": z, "v": field(z, _cross(*_xy(la, lo)) - xc0)})
        return out

    def test_weights_match_the_fit(self):
        from collectors import precip_shift as ps
        lat0, lon0 = 39.19, -120.27
        cells = self._cells(lat0, lon0, lambda z, xc: 1.0 + 0.4 * (z - 8010) / 1000 + 0.05 * xc)
        w, info = ps.line_weights(cells, lat0, lon0, 8010)
        self.assertAlmostEqual(sum(w), 1.0, places=9)                                   # agreeing cells pass through unchanged
        self.assertAlmostEqual(ps.estimate([c["v"] for c in cells], w), 1.0, places=6)  # an exactly linear field is recovered
        self.assertTrue(info["cross_crest"])
        w2, info2 = ps.line_weights(cells, lat0, lon0, 12000)                          # far above: capped 1,000 ft over the top cell
        self.assertEqual(info2["evaluated_at_ft"], 9100)
        self.assertAlmostEqual(ps.estimate([c["v"] for c in cells], w2), 1.0 + 0.4 * (9100 - 8010) / 1000, places=6)
        flat = [{**c, "z": 7000 + i} for i, c in enumerate(cells)]
        self.assertIsNone(ps.line_weights(flat, lat0, lon0, 8010)[0])
        self.assertEqual(ps.cell_height_ft(0.0), (6225.0, True))                        # Lake Tahoe water cell
        self.assertFalse(ps.cell_height_ft(2000)[1])
        self.assertEqual(ps.cell_height_ft(None), (None, False))

    def test_running_total_clip(self):
        from collectors import precip_shift as ps
        hi, lo = [0.0, 0.2, 0.2, 0.0], [0.3, 0.0, 0.1, 0.0]
        out = ps.shift_hourly([hi, lo], [1.5, -0.5])
        self.assertEqual(out[0], 0.0)                         # 1.5 x 0 - 0.5 x 0.3 < 0: clipped
        self.assertTrue(all(x >= 0 for x in out))
        self.assertAlmostEqual(sum(out), 1.5 * 0.4 - 0.5 * 0.4, places=9)
        self.assertIsNone(ps.shift_hourly([[0.1, None], [0.1, 0.1]], [0.5, 0.5])[1])

    def test_live_correction(self):
        from collectors.open_meteo_client import OpenMeteoClient
        times = [f"2026-11-24T{i:02d}:00" for i in range(6)]
        lat0, lon0 = 39.19, -120.27
        cells = self._cells(lat0, lon0, lambda z, xc: 0.1 * (1 + 0.4 * (z - 8010) / 1000))
        for c in cells:
            c["series"] = {t: c["v"] for t in times}
        out, info = OpenMeteoClient.corrected_precip(times, [0.08] * 6, cells, lat0, lon0, 8010, 1.2)
        self.assertAlmostEqual(sum(out), 6 * 0.1 * 1.2, places=3)                       # line at the tier, times the residual
        flat = [{**c, "z": 7000} for c in cells]
        out2, info2 = OpenMeteoClient.corrected_precip(times, [0.08] * 6, flat, lat0, lon0, 8010, 1.2)
        self.assertIn("fallback", info2)
        self.assertAlmostEqual(sum(out2), 6 * 0.08 * 1.2, places=3)                     # own cell, still times the residual
        c = OpenMeteoClient(blends=[], precip_correction={"residual": {"gem": 3.4, "icon": 1.1}, "residual_bounds": [0.5, 2.0]})
        self.assertEqual((c._correction_residual("gem"), c._correction_residual("icon"), c._correction_residual("ukmo")), (2.0, 1.1, 1.0))
        calls = []

        def fake(points, om_id):
            calls.append(om_id)
            return [{"latitude": la, "longitude": lo, "elevation": 0.0 if k == 0 else 2000 + 40 * k,
                     "hourly": {"time": times, "precipitation": [0.1] * 6}} for k, (la, lo) in enumerate(points)]
        c._query_points = fake
        pal = {"base": {"lat": 39.197, "lon": -120.2356}, "mid": {"lat": 39.198, "lon": -120.2791}, "summit": {"lat": 39.1982, "lon": -120.2873}}
        alp = {"base": {"lat": 39.1645, "lon": -120.2386}, "mid": {"lat": 39.157, "lon": -120.24}, "summit": {"lat": 39.144, "lon": -120.248}}
        n1 = c._fetch_neighborhoods(pal, ["ecmwf_ifs", "gfs_seamless"])
        c._fetch_neighborhoods(alp, ["ecmwf_ifs", "gfs_seamless"])
        self.assertEqual(calls, ["ecmwf_ifs", "gfs_seamless", "gfs_seamless"])      # the 9 km model's cells are reused for Alpine
        self.assertEqual(len(n1["ecmwf_ifs"]), 9)
        self.assertTrue(n1["ecmwf_ifs"][0]["lake"] and n1["ecmwf_ifs"][0]["z"] == 6225.0)

    def test_corrected_single_output(self):
        from collectors.open_meteo_client import OpenMeteoClient

        class Stub(OpenMeteoClient):
            def _assemble(self, m, parsed, *a):
                return {"status": "success", "model": {"id": m["id"], "label": m["label"]},
                        "primary_model": {"label": f"{m['label']} ({m['grid']})"}, "methodology": {}}

        c = Stub(blends=[], precip_correction={"method": "line + residual", "fitted": {"seasons": "WY2023-WY2027"}, "residual": {"icon": 1.17}})
        out = c._corrected_output({"id": "icon", "label": "ICON", "grid": "13 km"}, {}, {"residual": 1.17, "tiers": {}}, [], {}, True, "now")
        self.assertEqual((out["model"]["id"], out["model"]["label"], out["model"]["corrected"]), ("icon", "ICON (corrected)", True))  # same id: the toggle swaps files
        self.assertEqual(out["primary_model"]["label"], "ICON (13 km), precipitation corrected")
        self.assertEqual(out["precip_correction"]["members"]["icon"]["residual"], 1.17)

    def test_corrected_blend_members(self):
        from collectors.open_meteo_client import OpenMeteoClient

        class Stub(OpenMeteoClient):   # skip the summaries; this checks which members a blend takes
            def _summarize_tier(self, steps, *a):
                return {"steps": steps}

            def _assemble(self, m, parsed, *a):
                return {"status": "success", "model": dict(m), "primary_model": {}, "methodology": {}, "parsed": parsed}

        tiers = {k: {"lat": 39.19, "lon": -120.27, "elevation_m": 2400} for k in ("base", "mid", "summit")}
        steps = TestBlend._member(4, 1.0, 0.1, 25.0, 270)
        corrected = {mid: {k: {"_steps": steps} for k in tiers} for mid in ("ecmwf_hres", "icon")}
        outputs = {mid: {"status": "success", "model": {"runs": []}} for mid in ("ecmwf_hres", "icon", "nbm")}
        outputs["nbm"]["elevation_timelines"] = {k: steps for k in tiers}
        bl = {"id": "bc", "label": "Corrected blend", "members": {"ecmwf_hres": 1, "icon": 1, "nbm": 1}, "precip_correction": True, "min_weight_share": 0.5}
        labels = {"base": "Base", "mid": "Mid", "summit": "Summit"}
        bo = Stub(blends=[])._blend_output(bl, outputs, corrected, {}, {}, tiers, labels, {}, "now")
        self.assertEqual([x["id"] for x in bo["blend"]["members"]], ["ecmwf_hres", "icon"])   # NBM has no correction: left out
        self.assertEqual(bo["blend"]["missing"], ["NBM"])
        bo2 = Stub(blends=[])._blend_output({**bl, "precip_correction": False}, outputs, corrected, {}, {}, tiers, labels, {}, "now")
        self.assertEqual(len(bo2["blend"]["members"]), 3)                                    # a plain blend still takes NBM


class TestModelList(unittest.TestCase):
    """RRFS is a model and blend member but has no hindcast; the hindcast list doesn't follow the Equal blend."""

    def test_hindcast_models_and_refit(self):
        import tempfile
        from unittest import mock
        import blend_weights as bw
        from collectors.open_meteo_client import MODELS
        from collectors import precip_shift as ps
        rr = next(m for m in MODELS if m["id"] == "rrfs")
        self.assertEqual(rr["om"], "ncep_rrfs_conus")
        self.assertIn("ncep_rrfs_conus", ps.GRID_STEP_DEG)                 # it gets the elevation shift
        hm = bw.member_models()
        self.assertNotIn("rrfs", hm)                                       # no hindcast
        self.assertIn("gem", hm)                                           # still scored though out of the Equal blend
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config"; cfg.mkdir()
            (cfg / "sources.json").write_text(json.dumps({"blends": [{"id": "blend_skill", "label": "Skill", "members": {"icon": 1.1, "rrfs": 1.0, "gem": 0.9}}]}))
            with mock.patch.object(bw, "BASE_DIR", Path(tmp)):
                bw.apply_weights("blend_skill", {"icon": {"weight": 1.2, "mae": 0.4}, "gem": {"weight": 0.8, "mae": 0.6}},
                                 {"lead": "short lead", "site_days": 10, "period": "test", "created": "2026-11-25T00:00:00"})
            b = json.loads((cfg / "sources.json").read_text())["blends"][0]
            self.assertEqual(b["members"], {"icon": 1.2, "gem": 0.8, "rrfs": 1.0})   # RRFS kept at the average weight
            self.assertIn("rrfs unfitted", b["weights_note"])


class TestSkillReport(unittest.TestCase):
    """Storm grouping, out-of-sample bias correction, categorical scores, neighborhood estimates."""

    def test_storms_and_correction(self):
        from datetime import date
        import skill_report as sr
        st = sr.storms_from([{"date": "2025-02-12", "confirmed": True}, {"date": "2025-02-13", "confirmed": True},
                             {"date": "2025-02-20", "confirmed": True}, {"date": "2025-02-21", "confirmed": False}])
        self.assertEqual([len(s) for s in st], [2, 1])
        recs = []
        for wy in (2024, 2025, 2026):
            for k in range(20):
                obs = 0.2 + 0.05 * (k % 7)
                recs.append({"site": "SQV", "day": date(wy - 1, 12, 1 + k), "wy": wy, "obs": obs,
                             "fc": {"dry": obs * 0.6, "good": obs * 1.02}})
        res = sr.evaluate(recs, [], ["dry", "good"])
        self.assertLess(res["members_corrected"]["dry"]["day_mae"], 0.01)               # a constant 0.6x bias is removed
        self.assertGreater(res["members_raw"]["dry"]["day_mae"], 0.1)
        self.assertAlmostEqual(res["blends"]["equal corrected"]["day_bias"], 0.0, places=2)
        cat = sr.categorical([(0.6, 0.7), (0.2, 0.8), (0.9, 0.1), (0.1, 0.1)], 0.5)
        self.assertEqual((cat["hits"], cat["misses"], cat["false_alarms"]), (1, 1, 1))
        self.assertAlmostEqual(cat["csi"], 1 / 3)

    def test_neighborhood_estimates(self):
        from datetime import datetime, timedelta, timezone
        import neighborhood_hindcast as nh
        from collectors.nbm_downscale import _xy, _cross
        lat0, lon0 = nh.bw.HINDCAST_SITES["SQV"]
        t0 = datetime(2026, 2, 15, 12, tzinfo=timezone.utc)
        cells = {}
        xc0 = _cross(*_xy(lat0, lon0))
        for i, (di, dj, z) in enumerate([(0, 0, 7500), (1, 0, 7800), (-1, 0, 7000), (0, 1, 6800), (0, -1, 8100), (1, 1, 7300)]):
            la, lo = lat0 + di * 0.03, lon0 + dj * 0.04
            p = 1.0 + 0.4 * (z - 8010) / 1000 + 0.05 * (_cross(*_xy(la, lo)) - xc0)     # known field: +0.4 in per 1,000 ft
            cells[(la, lo)] = {"lat": la, "lon": lo, "elev_ft": z, "center": i == 0,
                               "series": {(t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M"): p / 24 for k in range(1, 25)}}
        est = nh.estimates_for_day(cells, "SQV", t0)
        self.assertAlmostEqual(est["elev-line"], 1.0, places=2)                    # the field's value at the pillow (8,010 ft)
        self.assertAlmostEqual(est["elev-match"], 1.0 + 0.4 * 0.09 + 0.05 * (_cross(*_xy(lat0, lon0 - 0.04)) - xc0), places=2)
        self.assertLess(est["center"], est["elev-line"])                            # the lower center cell is drier


class TestValuesAt(unittest.TestCase):
    """grib2_complex.values_at: exactly decode()'s numbers at any point, without building the field."""

    @staticmethod
    def _fields():
        import math
        smooth = [int(2600 + 80 * math.sin(k / 23.0) + 5 * math.cos(k / 3.0)) for k in range(2600)]
        noisy = [1500 + (k * 7919) % 523 + int(200 * math.sin(k / 50.0)) for k in range(2600)]   # groups wider than 6 bits
        flat = [0] * 400 + [12] * 300 + smooth[:900]                                              # constant (zero-width) groups
        return {"smooth": smooth, "noisy": noisy, "flat": flat}

    def test_matches_decode(self):
        from collectors.grib2_complex import decode, values_at
        for name, ints in self._fields().items():
            n = len(ints)
            idx = sorted({0, 1, 2, 3, 6, 7, 8, 13, 14, 299, 300, 301, 399, 400, 401, 699, 700, n // 2, n - 2, n - 1})
            for tmpl, order in ((3, 2), (3, 1), (2, 0)):
                for gl in (7, 64, 300):          # 300: runs longer than the popcount limit
                    s5, s7 = _pack_complex(ints, order=order, tmpl=tmpl, group_len=gl)
                    full = decode(s5, s7)
                    got = values_at(s5, s7, idx)
                    self.assertEqual(sorted(got), idx)
                    for i in idx:
                        self.assertEqual(got[i], full[i], (name, tmpl, order, gl, i))

    def test_missing_values_and_bad_requests(self):
        from collectors.grib2_complex import decode, values_at
        ints = self._fields()["smooth"][:500]
        s5, s7 = _pack_complex(ints, order=2, missing={5, 6, 250})
        full = decode(s5, s7)
        self.assertEqual(values_at(s5, s7, [5, 7, 499]), {5: None, 7: full[7], 499: full[499]})
        s5, s7 = _pack_complex(ints, order=2, group_len=25)
        with self.assertRaises(IndexError):
            values_at(s5, s7, [500])
        with self.assertRaises(ValueError):          # download cut before the point
            values_at(s5, s7[:len(s7) // 3], [480])

    def test_fast_unpack(self):
        import random
        from collectors.grib2_complex import _uints, _uints_fast
        rnd = random.Random(3)
        buf = bytes(rnd.randrange(256) for _ in range(3000))
        for width in list(range(0, 18)) + [23]:
            for bitpos in (0, 5, 13):
                count = (len(buf) * 8 - bitpos) // max(1, width) - 1
                self.assertEqual(_uints_fast(buf, bitpos, width, count), _uints(buf, bitpos, width, count), (width, bitpos))


def _lambert_s3(nx, ny, la1, lo1, lov=-97.5, latin=38.5, dx=3000.0, scan=0x40):
    """GRIB2 section 3, grid template 3.30 (Lambert conformal, spherical earth)."""
    import struct
    s = bytearray(81)
    s[0:4] = struct.pack(">I", 81); s[4] = 3; s[12:14] = struct.pack(">H", 30); s[14] = 6
    s[30:34] = struct.pack(">I", nx); s[34:38] = struct.pack(">I", ny)
    s[38:42] = struct.pack(">I", round(la1 * 1e6)); s[42:46] = struct.pack(">I", round((lo1 % 360) * 1e6))
    s[47:51] = struct.pack(">I", round(latin * 1e6)); s[51:55] = struct.pack(">I", round((lov % 360) * 1e6))
    s[55:59] = struct.pack(">I", round(dx * 1e3)); s[59:63] = struct.pack(">I", round(dx * 1e3)); s[64] = scan
    s[65:69] = struct.pack(">I", round(latin * 1e6)); s[69:73] = struct.pack(">I", round(latin * 1e6))
    return bytes(s)


def _grib_message(s3, s5, s7, cat, par, lev_type, lev_val, fh, disc=0):
    """One GRIB2 message (product template 4.0) around packed sections 5 and 7."""
    import struct
    s1 = struct.pack(">IB", 21, 1) + bytes(16)
    s4 = bytearray(34)
    s4[0:4] = struct.pack(">I", 34); s4[4] = 4; s4[7:9] = struct.pack(">H", 0)
    s4[9], s4[10], s4[17], s4[22], s4[23] = cat, par, 1, lev_type, 0
    s4[18:22] = struct.pack(">I", fh); s4[24:28] = struct.pack(">I", lev_val)
    body = s1 + s3 + bytes(s4) + s5 + struct.pack(">IBB", 6, 6, 255) + s7 + b"7777"
    return b"GRIB" + bytes([0, 0, disc, 2]) + struct.pack(">Q", 16 + len(body)) + body


class TestHRRRSLW(unittest.TestCase):
    """HRRR and RRFS supercooled liquid: index, cycle, column diagnostics, and runs on synthetic files."""

    HRRR = {"tmpl": 30, "radius": 6371229.0, "nx": 1799, "ny": 1059, "la1": 21.138123, "lo1": -122.719528, "lad": 38.5,
            "lov": -97.5, "dx": 3000.0, "dy": 3000.0, "scan": 0x40, "latin1": 38.5, "latin2": 38.5}
    NX = NY = 24
    PTS = {"pal": {"lat": 39.1982, "lon": -120.2873, "elevation_ft": 9050}, "alp": {"lat": 39.1467, "lon": -120.245, "elevation_ft": 8637}}

    @staticmethod
    def _profile():
        """6 °C at 775 hPa, 1 °C colder per 10 hPa (0 °C at 715 hPa). g/kg: supercooled cloud water at 650-550 hPa,
        cloud water at 750 hPa (above 0 °C), snow at 600-525, graupel at 575, drizzle at 550, cloud ice at 500."""
        from collectors.hrrr_slw import LEVELS_HPA
        prof = {p: {"t": 6.0 - 0.1 * (775 - p), "qc": 0.0, "qr": 0.0, "qs": 0.0, "qg": 0.0, "qi": 0.0} for p in LEVELS_HPA}
        for p in (650, 625, 600, 575, 550):
            prof[p]["qc"] = 0.2
        prof[750]["qc"] = 0.3
        for p in (600, 575, 550, 525):
            prof[p]["qs"] = 0.1
        prof[575]["qg"] = 0.05
        prof[550]["qr"] = 0.02
        prof[500]["qi"] = 0.03
        return prof

    PER_LAYER = 1e-3 * 100 / 9.80665 * 25      # 1 g/kg over a 25 hPa layer, in kg/m²

    def _build(self, fh, items):
        """GRIB2 messages on 24 x 24 cells of the real HRRR (and RRFS) 3 km grid, and their index.
        items: (name, level, category, parameter, level type, level value, value, decimal scale)."""
        from collectors import nbm_archive as na
        la1, lo1 = na.cell_latlon(self.HRRR, 241, 626)
        s3 = _lambert_s3(self.NX, self.NY, la1, lo1)
        npts = self.NX * self.NY
        tilt = [(k % self.NX - 10) + (k // self.NX - 10) for k in range(npts)]   # one packed unit per cell from (10, 10)
        data, lines = b"", []
        for name, level, cat, par, lev_type, lev_val, value, D in items:
            ints = [0] * npts if value == 0 else [round(value * 10 ** D) + t for t in tilt]
            s5, s7 = _pack_complex(ints, order=2, group_len=11, D=D)
            lines.append(f"{len(lines) + 1}:{len(data)}:d=2026112418:{name}:{level}:{fh} hour fcst:")
            data += _grib_message(s3, s5, s7, cat, par, lev_type, lev_val, fh)
        return data, "\n".join(lines) + "\n"

    def _file(self, fh, wrong_code_at=None, model="hrrr"):
        """A small pressure-level file (HRRR wrfprs or RRFS prslev) and its index. RRFS names cloud ice
        ICMR (1/23) and keeps the terrain height in its 2-D file (_sfc_file)."""
        from collectors.hrrr_slw import LEVELS_HPA
        prof, items = self._profile(), []
        ice = ("CIMIXR", (1, 82)) if model == "hrrr" else ("ICMR", (1, 23))
        for p in sorted(LEVELS_HPA):                 # the file runs from the top down
            lev = f"{p} mb"
            items += [("HGT", lev, 3, 5, 100, p * 100, 3000.0 if p == 700 else 1000.0, 1),
                      ("TMP", lev, 0, 0, 100, p * 100, 273.15 + prof[p]["t"], 1), ("RH", lev, 1, 1, 100, p * 100, 80.0, 1)]
            for name, (cat, par), key in (("CLMR", (1, 22), "qc"), (ice[0], ice[1], "qi"), ("RWMR", (1, 24), "qr"),
                                          ("SNMR", (1, 25), "qs"), ("GRLE", (1, 32), "qg")):
                if wrong_code_at == (name, p):
                    par = 25 if par != 25 else 22
                items.append((name, lev, cat, par, 100, p * 100, prof[p][key] / 1000.0, 7))
        if model == "hrrr":
            items.append(("HGT", "surface", 3, 5, 1, 0, 2400.0, 1))
        return self._build(fh, items)

    def _sfc_file(self, fh):
        """A small RRFS 2dfld-like file: terrain height between other 2-D fields."""
        return self._build(fh, [("TMP", "2 m above ground", 0, 0, 103, 2, 270.0, 1), ("HGT", "surface", 3, 5, 1, 0, 2350.0, 1),
                                ("HGT", "lowest bottom level of supercooled liquid water layer", 3, 5, 253, 0, 2600.0, 1)])

    def test_parse_idx(self):
        from collectors.nbm_archive import parse_idx
        from collectors.hrrr_slw import IDX_FIELDS
        idx = ("1:0:d=2026112418:HGT:700 mb:anl:\n2:500:d=2026112418:TMP:700 mb:anl:\n3:900:d=2026112418:RH:700 mb:anl:\n"
               "4:1000:d=2026112418:CLMR:700 mb:anl:\n5:1100:d=2026112418:TMP:2 m above ground:anl:\n6:1200:d=2026112418:HGT:surface:anl:\n")
        hrrr, rrfs = IDX_FIELDS["hrrr"], IDX_FIELDS["rrfs"]
        self.assertEqual(parse_idx(idx, 0, hrrr), {"HGT:700": (0, 499), "TMP:700": (500, 899), "CLMR:700": (1000, 1099), "HGT:surface": (1200, None)})
        fc = idx.replace("anl", "6 hour fcst")
        self.assertEqual(parse_idx(fc, 6, hrrr)["TMP:700"], (500, 899))
        self.assertEqual(parse_idx(fc, 5, hrrr), {})
        ice = "1:0:d=2026112412:CIMIXR:700 mb:12 hour fcst:\n2:70:d=2026112412:ICMR:700 mb:12 hour fcst:\n3:140:d=2026112412:RWMR:700 mb:12 hour fcst:\n"
        self.assertEqual(list(parse_idx(ice, 12, hrrr)), ["CIMIXR:700", "RWMR:700"])   # each model asks for its own ice name
        self.assertEqual(list(parse_idx(ice, 12, rrfs)), ["ICMR:700", "RWMR:700"])

    def test_latest_cycle(self):
        import urllib.error
        from datetime import datetime, timezone
        from unittest import mock
        from collectors import hrrr_slw as hs
        asked = []

        def fake_request(url, rng=None, **kw):
            asked.append(url.rsplit("/", 1)[-1])
            if "hrrr.20261124/conus/hrrr.t12z" in url:
                return b"1"
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        with mock.patch.object(hs, "_request", fake_request):
            self.assertEqual(hs.latest_cycle(datetime(2026, 11, 24, 19, 30, tzinfo=timezone.utc)), datetime(2026, 11, 24, 12, tzinfo=timezone.utc))
        self.assertEqual(asked, ["hrrr.t18z.wrfprsf48.grib2.idx", "hrrr.t12z.wrfprsf48.grib2.idx"])
        asked.clear()
        with mock.patch.object(hs, "_request", lambda url, rng=None, **kw: asked.append(url) or b"1"):
            self.assertEqual(hs.latest_cycle(datetime(2026, 11, 24, 19, 30, tzinfo=timezone.utc), "rrfs"), datetime(2026, 11, 24, 18, tzinfo=timezone.utc))
        self.assertEqual(asked, ["https://noaa-rrfs-ops-pds.s3.amazonaws.com/rrfs.20261124/18/rrfs.t18z.prslev.3km.f084.conus.grib2.idx"])
        c = datetime(2026, 11, 24, 6, tzinfo=timezone.utc)
        self.assertEqual(hs.file_url(c, 7), "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20261124/conus/hrrr.t06z.wrfprsf07.grib2")
        self.assertEqual(hs.file_url(c, 84, "rrfs", "sfc"), "https://noaa-rrfs-ops-pds.s3.amazonaws.com/rrfs.20261124/06/rrfs.t06z.2dfld.3km.f084.conus.grib2")
        with self.assertRaises(ValueError):
            hs.SLWClient("unused", "gfs")

    def test_heights_surface_and_layers(self):
        import math
        from collectors import hrrr_slw as hs
        lv = hs.LEVELS_HPA
        iso = [-10.0] * len(lv)                 # isothermal: z2 - z1 = (Rd T / g) ln(p1 / p2) exactly
        z = hs.level_heights(lv, iso, 3000.0)
        H = hs.RD * 263.15 / hs.G0
        for k, p in enumerate(lv):
            self.assertAlmostEqual(z[k], 3000.0 + H * math.log(700 / p), places=6)
        self.assertAlmostEqual(hs.surface_pressure(lv, z, iso, z[3]), lv[3], places=6)
        ps = hs.surface_pressure(lv, z, iso, 2400.0)
        self.assertAlmostEqual(ps, 700 * math.exp((3000 - 2400) / H), places=4)
        self.assertAlmostEqual(hs.surface_pressure(lv, z, iso, z[0] - 100), 775 * math.exp(100 / H), places=4)   # below 775 hPa
        w = hs.layer_weights(lv, ps)
        self.assertAlmostEqual(sum(w), ps - 450, places=9)
        self.assertEqual(w[0], 0.0)                                   # 775 hPa is below the surface
        self.assertAlmostEqual(w[1], ps - 737.5, places=9)            # lowest level above it reaches down to the surface
        self.assertEqual(w[2:-1], [25.0] * (len(lv) - 3))
        self.assertEqual(w[-1], 12.5)

    def test_derive_hour(self):
        from collectors import hrrr_slw as hs
        lv, prof = hs.LEVELS_HPA, self._profile()
        cell = {"t_c": [prof[p]["t"] for p in lv], "z700_m": 3000.0, **{k: [prof[p][k] for p in lv] for k in ("qc", "qr", "qs", "qg", "qi")}}
        d = hs.derive_hour(lv, cell, 2400.0, 9050 / 3.28084)
        self.assertTrue(750 < d["psfc_hpa"] < 775)
        self.assertAlmostEqual(d["slw_col_kg_m2"], (0.2 * 5 + 0.02) * self.PER_LAYER, places=4)
        self.assertAlmostEqual(d["rime_col_kg_m2"], (0.2 * 3 + 0.02) * self.PER_LAYER, places=4)
        self.assertAlmostEqual(d["graupel_col_kg_m2"], 0.05 * self.PER_LAYER, places=4)
        self.assertEqual([p for p, r in zip(lv, d["rime"]) if r], [600, 575, 550])
        self.assertEqual(d["slw"][lv.index(750)], 0.0)               # liquid above 0 °C is not supercooled
        self.assertAlmostEqual(d["slw"][lv.index(550)], 0.22)
        s = d["summit"]                                              # 2,758 m: between 725 and 700 hPa here, just above 0 °C
        self.assertTrue(700 < s["p_hpa"] < 725 and 0 < s["t_c"] < 1, s)
        self.assertEqual(s["slw_g_kg"], 0.0)

    def test_fetch_on_synthetic_file(self):
        import tempfile
        from datetime import datetime, timezone
        from unittest import mock
        from collectors import hrrr_slw as hs, nbm_archive as na
        cycle = datetime(2026, 11, 24, 18, tzinfo=timezone.utc)
        files, ranges = {}, []

        def server(wrong=None):
            def fake_get(url, rng=None, **kw):
                fh = int(url.split("wrfprsf")[1][:2])
                self.assertNotIn("2dfld", url)
                if fh not in files:
                    files[fh] = self._file(fh, wrong)
                data, idx = files[fh]
                if url.endswith(".idx"):
                    return idx.encode()
                ranges.append((fh, rng))
                return data[rng[0]:len(data) if rng[1] is None else rng[1] + 1]
            return fake_get

        now = datetime(2026, 11, 26, 16, 20, tzinfo=timezone.utc)      # hours 46-48 of the 18Z run are left
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(hs, "latest_cycle", lambda now=None, model="hrrr": cycle), \
                mock.patch.object(na, "HEAD_MIN", 64), mock.patch.object(hs, "_get", server()):
            client = hs.SLWClient(tmp, "hrrr", workers=1)
            r = client.fetch(self.PTS, now=now)
            self.assertEqual(r["status"], "success", r)
            pal, alp = r["points"]["pal"], r["points"]["alp"]
            self.assertEqual([h["time"] for h in pal["hours"]], ["2026-11-26T16:00Z", "2026-11-26T17:00Z", "2026-11-26T18:00Z"])
            self.assertEqual((pal["model"], pal["last_fh"], pal["fh_range"]), ("HRRR", 48, [46, 48]))
            self.assertEqual((pal["cell"]["i"], pal["cell"]["j"]), (10, 10))
            self.assertEqual((alp["cell"]["i"], alp["cell"]["j"]), (11, 7))
            self.assertEqual(pal["cell"]["terrain_ft"], round(2400 * 3.28084))
            h = pal["hours"][0]
            self.assertAlmostEqual(h["slw_col_kg_m2"], (0.2 * 5 + 0.02) * self.PER_LAYER, places=4)
            self.assertAlmostEqual(h["rime_col_kg_m2"], (0.2 * 3 + 0.02) * self.PER_LAYER, places=4)
            self.assertAlmostEqual(h["qi"][hs.LEVELS_HPA.index(500)], 0.03)
            self.assertAlmostEqual(alp["hours"][0]["qc"][hs.LEVELS_HPA.index(600)], 0.2 - 2e-4)      # its cell is 2 units lower
            # TMP read only as far as the cells; the five hydrometeor messages of a level (adjacent in the file) in one request
            data, idx = files[46]
            offs = {(ln.split(":")[3], ln.split(":")[4]): int(ln.split(":")[1]) for ln in idx.splitlines()}
            starts = sorted(offs.values()) + [len(data)]
            end_of = {o: starts[starts.index(o) + 1] - 1 for o in offs.values()}
            asked = [rng for fh, rng in ranges if fh == 46]
            for p in hs.LEVELS_HPA:
                a = offs[("TMP", f"{p} mb")]
                got = sum(b - x + 1 for x, b in asked if a <= x <= end_of[a])
                self.assertLess(got, end_of[a] - a + 1, p)
                self.assertIn((offs[("CLMR", f"{p} mb")], end_of[offs[("GRLE", f"{p} mb")]]), asked)
            self.assertTrue(Path(tmp, "hrrr_slw_2026112418.json").exists())
            ranges.clear()
            again = client.fetch(self.PTS, now=now)
            self.assertEqual(ranges, [])
            self.assertTrue(again["points"]["pal"]["download"]["from_cache"])
            self.assertEqual(again["points"]["pal"]["hours"], pal["hours"])
        files.clear()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(hs, "latest_cycle", lambda now=None, model="hrrr": cycle), \
                mock.patch.object(hs, "_get", server(wrong=("CLMR", 600))):
            r = hs.SLWClient(tmp, "hrrr", workers=1).fetch(self.PTS, now=now)
        self.assertEqual(r["status"], "error")
        self.assertIn("GRIB2 codes", r["error_message"])

    def test_fetch_rrfs_on_synthetic_files(self):
        """RRFS: three-digit hours to 84, ICMR for cloud ice, terrain from the 2-D file, its own cache."""
        import re
        import tempfile
        from datetime import datetime, timezone
        from unittest import mock
        from collectors import hrrr_slw as hs, nbm_archive as na
        cycle = datetime(2026, 11, 24, 18, tzinfo=timezone.utc)
        files, asked = {}, []

        def fake_get(url, rng=None, **kw):
            m = re.search(r"/rrfs\.20261124/18/rrfs\.t18z\.(prslev|2dfld)\.3km\.f(\d{3})\.conus\.grib2", url)
            self.assertIsNotNone(m, url)
            kind, fh = m.group(1), int(m.group(2))
            if (kind, fh) not in files:
                files[kind, fh] = self._file(fh, model="rrfs") if kind == "prslev" else self._sfc_file(fh)
            data, idx = files[kind, fh]
            if url.endswith(".idx"):
                return idx.encode()
            asked.append((kind, fh))
            return data[rng[0]:len(data) if rng[1] is None else rng[1] + 1]

        now = datetime(2026, 11, 28, 4, 20, tzinfo=timezone.utc)      # hours 82-84 of the 18Z run are left
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(hs, "latest_cycle", lambda now=None, model="hrrr": cycle), \
                mock.patch.object(na, "HEAD_MIN", 64), mock.patch.object(hs, "_get", fake_get):
            r = hs.SLWClient(tmp, "rrfs", workers=1).fetch(self.PTS, now=now)
            self.assertEqual(r["status"], "success", r)
            pal = r["points"]["pal"]
            self.assertEqual((pal["model"], pal["last_fh"], pal["fh_range"]), ("RRFS", 84, [82, 84]))
            self.assertEqual([h["time"] for h in pal["hours"]], ["2026-11-28T04:00Z", "2026-11-28T05:00Z", "2026-11-28T06:00Z"])
            self.assertEqual(pal["cell"]["terrain_ft"], round(2350 * 3.28084))                # from the 2-D file
            self.assertEqual(sorted({fh for kind, fh in asked if kind == "2dfld"}), [82, 83])   # terrain from the first hours only
            h = pal["hours"][0]
            self.assertAlmostEqual(h["qi"][hs.LEVELS_HPA.index(500)], 0.03)                    # ICMR
            self.assertAlmostEqual(h["slw_col_kg_m2"], (0.2 * 5 + 0.02) * self.PER_LAYER, places=4)
            self.assertAlmostEqual(h["rime_col_kg_m2"], (0.2 * 3 + 0.02) * self.PER_LAYER, places=4)
            self.assertTrue(Path(tmp, "rrfs_slw_2026112418.json").exists())
            self.assertFalse(Path(tmp, "hrrr_slw_2026112418.json").exists())

    def test_prune_per_model(self):
        import tempfile
        from collectors import hrrr_slw as hs
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("hrrr", "rrfs"):
                for k in range(6):
                    Path(tmp, f"{m}_slw_202611{20 + k}00.json").write_text("{}")
            hs.SLWClient(tmp, "hrrr")._prune()
            self.assertEqual(sorted(x.name for x in Path(tmp).glob("hrrr_slw_*.json")),
                             [f"hrrr_slw_202611{20 + k}00.json" for k in range(6 - hs.KEEP_CYCLES, 6)])
            self.assertEqual(len(list(Path(tmp).glob("rrfs_slw_*.json"))), 6)
