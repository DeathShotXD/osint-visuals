"""Offline tests for the conflict-events graphic. No network: the basemap is switched off in the page tests."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "conflict", "demo-events.csv")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


conflict = load("skills/conflict-events/scripts/conflict.py", "conflict")


def page_data(path):
    s = open(path, encoding="utf-8").read()
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


class Parse(unittest.TestCase):
    def test_demo_parses(self):
        events, meta = conflict.parse(conflict.load(DEMO))
        self.assertEqual(len(events), 24)
        self.assertEqual(meta["skipped"], 0)
        self.assertEqual(events[0]["month"], "2026-01")
        self.assertEqual(meta["columns"]["lat"], "latitude")

    def test_bad_rows_are_skipped(self):
        rows = [
            {"date_start": "2026-01-05", "latitude": "10", "longitude": "20", "best": "2"},
            {"date_start": "2026-01-06", "latitude": "999", "longitude": "20", "best": "2"},
            {"date_start": "nonsense", "latitude": "10", "longitude": "20", "best": "2"},
        ]
        events, meta = conflict.parse(rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(meta["skipped"], 2)

    def test_year_only_dates(self):
        rows = [{"year": "2025", "latitude": "1", "longitude": "2"}]
        events, _ = conflict.parse(rows)
        self.assertEqual(events[0]["month"], "2025-01")


class Aggregate(unittest.TestCase):
    def setUp(self):
        events, _ = conflict.parse(conflict.load(DEMO))
        self.data = conflict.aggregate(events)

    def test_totals(self):
        self.assertEqual(self.data["total_events"], 24)
        self.assertEqual(self.data["total_deaths"], 90)
        self.assertEqual(self.data["total_high"], 124)
        self.assertEqual(self.data["total_civilians"], 24)

    def test_monthly_is_continuous(self):
        months = [m["month"] for m in self.data["monthly"]]
        self.assertEqual(months[0], "2026-01")
        self.assertEqual(months[-1], "2026-08")
        self.assertEqual(len(months), 8)
        self.assertEqual(sum(m["events"] for m in self.data["monthly"]), 24)

    def test_types_and_countries(self):
        labels = [t["label"] for t in self.data["types"]]
        self.assertEqual(labels[0], "State-based conflict")
        self.assertEqual(self.data["types"][0]["events"], 10)
        self.assertEqual(self.data["countries"][0]["country"], "Invented Republic of Vireo")
        self.assertEqual(len(self.data["countries"]), 3)

    def test_bbox(self):
        self.assertAlmostEqual(self.data["bbox"][0], 20.0, places=1)
        self.assertAlmostEqual(self.data["bbox"][3], -24.0, places=1)
        self.assertEqual(self.data["range"], ["2026-01", "2026-08"])


class Page(unittest.TestCase):
    def test_page_written_without_basemap(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "c.html")
            conflict.main([DEMO, "--title", "T", "--source", "S", "--no-basemap", "--out", dest])
            data = page_data(dest)
            self.assertEqual(data["total_events"], 24)
            self.assertEqual(data["basemap"], [])

    def test_filters(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "c.html")
            conflict.main([DEMO, "--type", "1", "--no-basemap", "--out", dest])
            data = page_data(dest)
            self.assertEqual(data["total_events"], 10)
            self.assertTrue(all(e["type"] == "1" for e in data["events"]))

    def test_empty_after_filter_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                conflict.main([DEMO, "--country", "Nowhere", "--no-basemap", "--out", os.path.join(d, "c.html")])

    def test_input_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "e.csv"), os.path.join(d, "c.html")
            open(src, "w").write("date_start,latitude,longitude,country\n"
                                 "2026-01-01,10,20,\"</script><b>PROOF</b>\"\n")
            conflict.main([src, "--no-basemap", "--out", dest])
            s = open(dest, encoding="utf-8").read()
            self.assertNotIn("<b>PROOF</b>", s)
            self.assertIn("\\u003c/script", s)


if __name__ == "__main__":
    unittest.main()