"""Offline tests for the incident map. The demo counts are invented; the country outlines here are synthetic."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "incidents", "demo-incidents.csv")

GEO = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"NAME": "France", "ISO_A2": "FR", "ISO_A3": "FRA", "SOVEREIGNT": "France"},
     "geometry": {"type": "Polygon", "coordinates": [[[0, 42], [8, 42], [8, 50], [0, 50], [0, 42]]]}},
    {"type": "Feature", "properties": {"NAME": "Fr. S. Antarctic Lands", "ISO_A2": "FR", "ISO_A3": "ATF",
                                       "SOVEREIGNT": "France"},
     "geometry": {"type": "Polygon", "coordinates": [[[60, -50], [70, -50], [70, -40], [60, -40], [60, -50]]]}},
]}

SOV = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"NAME": "France", "ISO_A2": "-99", "ISO_A3": "-99", "ISO_A2_EH": "FR",
                                       "SOVEREIGNT": "France"},
     "geometry": {"type": "Polygon", "coordinates": [[[0, 42], [8, 42], [8, 50], [0, 50], [0, 42]]]}},
    {"type": "Feature", "properties": {"NAME": "Fr. S. Antarctic Lands", "ISO_A2": "FR", "ISO_A3": "ATF",
                                       "SOVEREIGNT": "France"},
     "geometry": {"type": "Polygon", "coordinates": [[[60, -50], [70, -50], [70, -40], [60, -40], [60, -50]]]}},
    {"type": "Feature", "properties": {"NAME": "Antarctica", "ISO_A2": "AQ", "ISO_A3": "ATA",
                                       "SOVEREIGNT": "Antarctica"},
     "geometry": {"type": "Polygon", "coordinates": [[[0, -80], [10, -80], [10, -70], [0, -70], [0, -80]]]}},
    {"type": "Feature", "properties": {"NAME": "C\u00f4te d'Ivoire", "ISO_A2": "CI", "ISO_A3": "CIV",
                                       "SOVEREIGNT": "Ivory Coast"},
     "geometry": {"type": "Polygon", "coordinates": [[[-8, 4], [-2, 4], [-2, 10], [-8, 10], [-8, 4]]]}},
]}


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


incident = load("skills/incident-map/scripts/incident.py", "incident")


def page_data(path):
    s = open(path, encoding="utf-8").read()
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


class Countries(unittest.TestCase):
    def test_dependencies_do_not_hijack_codes(self):
        idx = incident.country_index(GEO)
        self.assertEqual(idx["fr"], "France")
        self.assertEqual(idx["france"], "France")
        self.assertEqual(idx["fr. s. antarctic lands"], "Fr. S. Antarctic Lands")

    def test_sovereign_codes_beyond_dependencies(self):
        idx = incident.country_index(SOV)
        self.assertEqual(idx["fr"], "France")            # a sovereign beats a dependency for a shared code
        self.assertEqual(idx["aq"], "Antarctica")        # Antarctica keeps its own code
        self.assertEqual(idx["ata"], "Antarctica")
        self.assertEqual(idx["ivory coast"], "Côte d'Ivoire")   # the sovereign spelling is an alias
        self.assertEqual(idx["ci"], "Côte d'Ivoire")

    def test_view_countries(self):
        countries, view = incident.view_countries(GEO, {"France"})
        self.assertEqual([c["name"] for c in countries], ["France"])
        self.assertLessEqual(view[0], 0)
        self.assertGreater(view[3], 50)


class Parse(unittest.TestCase):
    def setUp(self):
        idx = incident.country_index(GEO)
        self.rows = incident.load(DEMO)
        self.events, self.meta = incident.parse(self.rows, idx)

    def test_org_column_is_ignored(self):
        self.assertEqual(self.meta["ignored"], ["organization"])
        keys = {k for e in self.events for k in e}
        self.assertNotIn("organization", keys)

    def test_counts(self):
        self.assertEqual(self.meta["rows"], 25)
        self.assertEqual(len(self.events), 25)
        self.assertEqual(sum(e["n"] for e in self.events), 38)
        self.assertEqual({e["m"] for e in self.events}.__len__(), 8)

    def test_unknown_country_kept_but_flagged(self):
        rows = [{"date": "2026-01-01", "country": "Atlantis", "sector": "Energy", "count": "2"}]
        events, meta = incident.parse(rows, incident.country_index(GEO))
        self.assertEqual(events[0]["c"], "Atlantis")
        self.assertIn("Atlantis", meta["unmapped"])

    def test_month_variants(self):
        rows = [{"year": "2025", "month": "", "country": "France"},
                {"year": "", "month": "2025-04", "country": "France"}]
        events, _ = incident.parse(rows, incident.country_index(GEO))
        self.assertEqual(events[0]["m"], "2025-01")
        self.assertEqual(events[1]["m"], "2025-04")


class Page(unittest.TestCase):
    def test_page_without_basemap(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "i.html")
            incident.main([DEMO, "--title", "T", "--source", "S", "--no-basemap", "--out", dest])
            data = page_data(dest)
            self.assertEqual(data["total"], 38)
            self.assertEqual(data["basemap"], [])
            self.assertEqual(len(data["countries"]), 12)

    def test_sector_filter(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "i.html")
            incident.main([DEMO, "--sector", "Energy", "--no-basemap", "--out", dest])
            data = page_data(dest)
            self.assertTrue(all(e["s"] == "Energy" for e in data["events"]))

    def test_empty_after_filter(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                incident.main([DEMO, "--sector", "Nowhere", "--no-basemap", "--out", os.path.join(d, "i.html")])

    def test_input_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "e.csv"), os.path.join(d, "i.html")
            open(src, "w").write("date,country,sector,count\n2026-01-01,\"</script><b>PROOF</b>\",Energy,1\n")
            incident.main([src, "--no-basemap", "--out", dest])
            s = open(dest, encoding="utf-8").read()
            self.assertNotIn("<b>PROOF</b>", s)
            self.assertIn("\\u003c/script", s)


if __name__ == "__main__":
    unittest.main()