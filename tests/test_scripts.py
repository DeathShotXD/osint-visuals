"""Offline tests for the four scripts (no network). Run: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


track = load("skills/track-map/scripts/track.py", "track")
shadow = load("skills/shadow-diagram/scripts/shadow.py", "shadow")
diorama = load("skills/scene-diorama/scripts/diorama.py", "diorama")
locator = load("skills/locator-map/scripts/locator.py", "locator")


def page_data(path):
    s = open(path, encoding="utf-8").read()
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


class Track(unittest.TestCase):
    def test_demo_findings(self):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_demo_data.py")], check=True, capture_output=True)
        tracks, skipped, _ = track.read_tracks(os.path.join(ROOT, "examples", "track", "demo-tankers.csv"))
        out, gaps, jumps, meets = track.analyse(tracks, 2 * 3600, 50, 1.0, 30 * 60)
        self.assertEqual(skipped, 0)
        self.assertEqual(len(gaps), 1); self.assertEqual(gaps[0]["hours"], 31.0)
        self.assertEqual([n["track"] for n in gaps[0]["near"]], ["KESTREL BAY"])
        self.assertEqual(len(jumps), 1); self.assertTrue(jumps[0]["outlier"])
        self.assertEqual(len(meets), 1); self.assertLess(meets[0]["min_km"], 1)
        drawn = next(t for t in out if t["id"] == "MERIDIAN STAR")["pts"]
        self.assertFalse(any(abs(p[1] - 22.40) < 1e-6 for p in drawn), "the bad fix must not be drawn")

    def test_times_and_spans(self):
        self.assertEqual(track.parse_span("2h"), 7200); self.assertEqual(track.parse_span("30m"), 1800)
        self.assertEqual(track.parse_time("1781000000").year, 2026)
        self.assertEqual(track.parse_time("2026-06-10T00:00:00Z").hour, 0)
        self.assertEqual(track.parse_time("2026-06-10 03:00").tzinfo is not None, True)

    def test_page_written(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "t.html")
            track.main([os.path.join(ROOT, "examples", "track", "demo-tankers.csv"), "--title", "T", "--out", dest])
            data = page_data(dest)
            self.assertEqual(len(data["tracks"]), 2); self.assertIn("gaps", data)


class Shadow(unittest.TestCase):
    def test_known_noon_elevation(self):
        # London at the December solstice: the sun peaks at about 15 degrees
        from datetime import timezone
        az, el = shadow.sun_position(51.5, -0.12, datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc))
        self.assertAlmostEqual(el, 15.0, delta=0.3); self.assertAlmostEqual(az, 180, delta=2)

    def test_demo_window_and_claim(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "s.html")
            shadow.main(["--lat", "-1.2864", "--lon", "36.8172", "--date", "2026-08-10", "--tz", "+03:00", "--shadow-azimuth", "250",
                         "--tolerance", "6", "--height", "1.75", "--shadow-length", "2.3", "--claimed", "16:30", "--out", dest])
            data = page_data(dest)
            self.assertEqual(len(data["windows"]), 1)
            w = data["windows"][0]; self.assertTrue(8 * 60 < w["from"] < w["to"] < 11 * 60)
            self.assertFalse(data["claim"]["fits"]); self.assertGreater(data["claim"]["off_by"], 90)

    def test_zone_names(self):
        tz, label = shadow.parse_tz("Africa/Nairobi"); self.assertEqual(label, "Africa/Nairobi")
        tz, label = shadow.parse_tz("-05:30"); self.assertEqual(tz.utcoffset(None).total_seconds(), -5.5 * 3600)


class Diorama(unittest.TestCase):
    def test_clip_polygon(self):
        sq = diorama.clip_poly([(-200, -200), (200, -200), (200, 200), (-200, 200)], 100)
        self.assertEqual(sorted(sq), sorted([(-100, -100), (100, -100), (100, 100), (-100, 100)]))
        self.assertEqual(diorama.clip_poly([(300, 300), (400, 300), (400, 400)], 100), [])

    def test_clip_line(self):
        pieces = diorama.clip_line([(-300, 0), (300, 0)], 100)
        self.assertEqual(pieces, [[(-100.0, 0.0), (100.0, 0.0)]])

    def test_join_rings(self):
        a, b = [(0, 0), (1, 0), (1, 1)], [(1, 1), (0, 1), (0, 0)]
        rings = diorama.join_rings([a, b]); self.assertEqual(len(rings), 1); self.assertEqual(rings[0][0], rings[0][-1])
        rings = diorama.join_rings([a, list(reversed(b))]); self.assertEqual(len(rings), 1)

    def test_heights(self):
        self.assertEqual(diorama.height_of({"height": "21 m"}), 21.0)
        self.assertAlmostEqual(diorama.height_of({"building:levels": "4"}), 4 * 3.2 + 1.2)
        self.assertEqual(diorama.height_of({"building": "house"}), 7)


class Locator(unittest.TestCase):
    def test_simplify_keeps_rings_closed(self):
        ring = [[0, 0], [1, 0.001], [2, 0], [2, 2], [1, 2.001], [0, 2], [0, 0]]
        s = locator.simplify_ring(ring, 0.01)
        self.assertEqual(s[0], s[-1]); self.assertGreaterEqual(len(s), 5)

    def test_point_in_polygon(self):
        sq = [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]
        self.assertTrue(locator.contains(sq, 5, 5)); self.assertFalse(locator.contains(sq, 15, 5))


if __name__ == "__main__":
    unittest.main()
