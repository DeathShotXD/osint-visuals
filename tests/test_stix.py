"""Offline tests for the STIX timeline. No network: the demo bundle is fictional and local."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "stix", "demo-campaign.json")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


stix = load("skills/stix-timeline/scripts/stix.py", "stix")


def page_data(path):
    s = open(path, encoding="utf-8").read()
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


class Parse(unittest.TestCase):
    def test_times(self):
        self.assertEqual(stix.parse_time("2026-02-03T08:30:00Z").year, 2026)
        self.assertEqual(stix.parse_time("2026-02-03").day, 3)
        self.assertIsNone(stix.parse_time("not a date"))
        self.assertIsNone(stix.parse_time(None))


class Demo(unittest.TestCase):
    def setUp(self):
        self.objects = stix.load(DEMO)
        self.data = stix.build(self.objects)

    def test_counts_and_lanes(self):
        self.assertEqual(len(self.data["events"]), 13)
        self.assertEqual(self.data["counts"]["actor"], 1)
        self.assertEqual(self.data["counts"]["malware"], 2)
        self.assertEqual(self.data["counts"]["technique"], 3)
        self.assertEqual(self.data["skipped"], 0)
        self.assertEqual(self.data["range"][0][:10], "2026-01-12")
        self.assertEqual(self.data["range"][1][:10], "2026-06-02")

    def test_ranges_and_dates(self):
        campaign = next(e for e in self.data["events"] if e["lane"] == "campaign")
        self.assertEqual(campaign["start"][:10], "2026-02-03")
        self.assertEqual(campaign["end"][:10], "2026-05-20")
        indicator = next(e for e in self.data["events"] if e["lane"] == "indicator")
        self.assertEqual(indicator["end"][:10], "2026-04-30")

    def test_relationships(self):
        self.assertEqual(len(self.data["links"]), 9)
        pairs = {(l["from"], l["kind"], l["to"]) for l in self.data["links"]}
        self.assertIn(("SABLE KITE", "uses", "OPERATION GLASS HARBOR"), pairs)
        self.assertIn(("update-check.example", "indicates", "GRAYFIN loader"), pairs)

    def test_confidence_filter(self):
        high = stix.build(self.objects, min_confidence=60)
        self.assertTrue(all(e["confidence"] >= 60 for e in high["events"]))
        self.assertLess(len(high["events"]), len(self.data["events"]))
        self.assertEqual(high["counts"]["technique"], 0)

    def test_objects_without_dates_are_skipped(self):
        objs = [{"type": "threat-actor", "id": "threat-actor--x", "name": "No date"}]
        data = stix.build(objs)
        self.assertEqual(data["events"], [])
        self.assertEqual(data["skipped"], 1)


class Page(unittest.TestCase):
    def test_page_written(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "t.html")
            stix.main([DEMO, "--title", "T", "--source", "S", "--out", dest])
            data = page_data(dest)
            self.assertEqual(len(data["events"]), 13)
            self.assertEqual(data["title"], "T")
            self.assertEqual(data["source"], "S")

    def test_input_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "b.json"), os.path.join(d, "b.html")
            bundle = {"type": "bundle", "objects": [
                {"type": "threat-actor", "id": "threat-actor--x", "name": "</script><b>PROOF</b>",
                 "created": "2026-01-01T00:00:00Z"}]}
            json.dump(bundle, open(src, "w"))
            stix.main([src, "--out", dest])
            s = open(dest, encoding="utf-8").read()
            self.assertNotIn("<b>PROOF</b>", s)
            self.assertIn("\\u003c/script", s)


if __name__ == "__main__":
    unittest.main()