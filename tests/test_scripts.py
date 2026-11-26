"""Offline tests for the four scripts (no network). Run: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


track = load("skills/track-map/scripts/track.py", "track")
shadow = load("skills/shadow-diagram/scripts/shadow.py", "shadow")
diorama = load("skills/scene-diorama/scripts/diorama.py", "diorama")
locator = load("skills/locator-map/scripts/locator.py", "locator")
before_after = load("skills/before-after/scripts/before_after.py", "before_after")
story = load("skills/scroll-story/scripts/story.py", "story")


def make_png(pixels, w, h):
    """A small RGBA PNG from a flat list of (r, g, b, a) tuples, using the standard library only."""
    import struct, zlib
    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in pixels[y * w:(y + 1) * w]) for y in range(h))
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def page_data(path):
    s = Path(path).read_text(encoding="utf-8")
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


class BeforeAfter(unittest.TestCase):
    def test_png_and_clear_score(self):
        land, cloud, empty = (120, 100, 70, 255), (230, 232, 235, 255), (0, 0, 0, 0)
        self.assertEqual(before_after.clear_score(make_png([land] * 16, 4, 4)), 1.0)
        self.assertEqual(before_after.clear_score(make_png([empty] * 16, 4, 4)), 0.0)
        self.assertAlmostEqual(before_after.clear_score(make_png([land] * 8 + [cloud] * 4 + [empty] * 4, 4, 4)), 0.5)
        w, h, ch, rows = before_after.png_pixels(make_png([land] * 6, 3, 2)); self.assertEqual((w, h, ch, rows[1][0]), (3, 2, 4, 120))

    def test_own_images(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, dest = os.path.join(d, "a.png"), os.path.join(d, "b.png"), os.path.join(d, "ba.html")
            Path(a).write_bytes(make_png([(10, 20, 30, 255)] * 4, 2, 2)); Path(b).write_bytes(make_png([(200, 20, 30, 255)] * 4, 2, 2))
            before_after.main(["--before-image", a, "--after-image", b, "--before-label", "1 Jan", "--after-label", "2 Feb",
                               "--credit", "Test images", "--mark", "40%,60%,Bridge", "--out", dest])
            data = page_data(dest)
            self.assertEqual(data["labels"], ["1 Jan", "2 Feb"]); self.assertTrue(data["imgs"][0].startswith("data:image/png;base64,"))
            self.assertEqual(data["marks"], [{"x": 0.4, "y": 0.6, "t": "Bridge"}])


class ScrollStory(unittest.TestCase):
    def test_demo_parses(self):
        demo = os.path.join(ROOT, "examples", "scroll-story", "demo.md")
        meta, steps, credits = story.parse(Path(demo).read_text(encoding="utf-8"), os.path.dirname(demo))
        self.assertEqual([s["kind"] for s in steps], ["map", "map", "map", "compare", "image", "text"])
        self.assertEqual(steps[2]["marker"]["label"], "Lahaina"); self.assertEqual(steps[2]["pitch"], 45)
        self.assertEqual(steps[3]["labels"], ["29 Jul 2023", "18 Aug 2023"]); self.assertIn("NASA", credits[0])

    def test_text_is_escaped(self):
        h = story.inline("A <script>x</script> **bold** and [link](https://example.org)")
        self.assertNotIn("<script>", h); self.assertIn("<strong>bold</strong>", h); self.assertIn('href="https://example.org"', h)
        self.assertNotIn("href", story.inline("[bad](javascript:alert(1))"))

    def test_page_and_svelte_export(self):
        demo = os.path.join(ROOT, "examples", "scroll-story", "demo.md")
        with tempfile.TemporaryDirectory() as d:
            dest, app = os.path.join(d, "s.html"), os.path.join(d, "app")
            story.main([demo, "--out", dest, "--svelte", app])
            data = page_data(dest); self.assertTrue(data["steps"][3]["before"].startswith("data:image/jpeg;base64,"))
            js = json.load(open(os.path.join(app, "src", "story.json"), encoding="utf-8"))
            self.assertEqual(js["steps"][3]["before"], "media/lahaina-2023-07-29.jpg")
            self.assertTrue(os.path.exists(os.path.join(app, "public", "media", "lahaina-2023-08-18.jpg")))
            self.assertTrue(os.path.exists(os.path.join(app, "src", "lib", "Scrolly.svelte")))


class Escape(unittest.TestCase):
    """An input value must never be able to close the <script> block that carries the page data."""

    def test_track_values_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            csvp, dest = os.path.join(d, "x.csv"), os.path.join(d, "x.html")
            Path(csvp).write_text("vessel,timestamp,lat,lon\n"
                                  "</script><b>PROOF</b>,2026-06-09T06:00:00Z,24.0,58.0\n"
                                  "SAFE,2026-06-09T08:00:00Z,24.2,58.2\n")
            track.main([csvp, "--source", "</script><b>PROOF</b>", "--out", dest])
            s = Path(dest).read_text(encoding="utf-8")
            self.assertNotIn("<b>PROOF</b>", s)
            self.assertIn("\\u003c/script", s)

    def test_story_metadata_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "s.md"), os.path.join(d, "s.html")
            Path(src).write_text("---\ntitle: t\nsources: </script><b>PROOF</b>\n---\n\n[text]\nHello.\n")
            story.main([src, "--out", dest])
            self.assertNotIn("<b>PROOF</b>", Path(dest).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
