"""Offline tests for geolocation-board (no network). Run: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


board = load("skills/geolocation-board/scripts/board.py", "board")
DEMO = os.path.join(ROOT, "skills", "geolocation-board", "assets", "demo.json")


def page_data(path):
    s = Path(path).read_text(encoding="utf-8")
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


def demo():
    with open(DEMO, encoding="utf-8") as f:
        return json.load(f)


class SunPosition(unittest.TestCase):
    def test_nairobi_afternoon(self):
        when = datetime(2026, 8, 10, 16, 0, tzinfo=timezone(timedelta(hours=3)))
        az, el = board.sun_position(-1.2864, 36.8172, when)
        self.assertAlmostEqual(az, 290.7, delta=0.4)
        self.assertAlmostEqual(el, 37.4, delta=0.4)

    def test_london_june_noon_is_high(self):
        when = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        az, el = board.sun_position(51.5, 0.0, when)
        self.assertGreater(el, 60.0)
        self.assertLess(el, 64.0)

    def test_angle_diff_wraps(self):
        self.assertAlmostEqual(board.angle_diff(350, 10), 20.0)
        self.assertAlmostEqual(board.angle_diff(10, 350), 20.0)
        self.assertAlmostEqual(board.angle_diff(0, 180), 180.0)


class TimeZone(unittest.TestCase):
    def test_offset(self):
        tz, label = board.parse_tz("+03:00")
        self.assertEqual(label, "+03:00")
        self.assertEqual(tz.utcoffset(None), timedelta(hours=3))

    def test_utc(self):
        tz, label = board.parse_tz("UTC")
        self.assertEqual(label, "UTC")
        self.assertEqual(tz.utcoffset(None), timedelta(0))

    def test_bad(self):
        with self.assertRaises(ValueError):
            board.parse_tz("+99:00")
        with self.assertRaises(ValueError):
            board.parse_tz("")


class Normalise(unittest.TestCase):
    def test_demo_scores_three_of_four(self):
        d = board.normalise(demo())
        self.assertEqual(d["score"], 3)
        self.assertEqual(d["max"], 4)
        self.assertEqual(d["gaps"], 1)
        self.assertEqual(d["core_count"], 4)

    def test_demo_sun_fits(self):
        s = board.normalise(demo())["sun"]
        self.assertFalse(s["missing"])
        self.assertAlmostEqual(s["expected_shadow"], 76.1, delta=0.2)
        self.assertAlmostEqual(s["shadow_diff"], 6.1, delta=0.2)
        self.assertTrue(s["shadow_fits"])
        self.assertAlmostEqual(s["expected_length"], 2.44, delta=0.05)
        self.assertTrue(s["length_fits"])

    def test_bad_bearing(self):
        d = demo()
        d["features"][0]["bearing_deg"] = 400
        with self.assertRaises(SystemExit):
            board.normalise(d)

    def test_bad_distance(self):
        d = demo()
        d["features"][0]["distance_m"] = 0
        with self.assertRaises(SystemExit):
            board.normalise(d)

    def test_no_core_checks_falls_back_to_all(self):
        d = demo()
        d["checks"] = [{"label": "one", "ok": True}, {"label": "two", "ok": False}]
        out = board.normalise(d)
        self.assertEqual(out["max"], 2)
        self.assertEqual(out["score"], 1)

    def test_missing_place_has_no_sun(self):
        d = demo()
        for k in ("lat", "lon", "date", "tz", "claimed_time"):
            d.pop(k, None)
        out = board.normalise(d)
        self.assertTrue(out["sun"]["missing"])


class Escaping(unittest.TestCase):
    def test_page_json_escapes_angle_brackets(self):
        s = board.page_json({"x": "</script><b>PROOF</b>"})
        self.assertIn("\\u003c/script", s)
        self.assertNotIn("</script>", s)

    def test_input_cannot_close_the_data_block(self):
        d = demo()
        d["title"] = "<b>T</b>"
        d["features"][0]["label"] = "</script><b>PROOF</b>"
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "b.json")
            dest = os.path.join(tmp, "b.html")
            with open(src, "w", encoding="utf-8") as f:
                json.dump(d, f)
            board.main([src, "--out", dest])
            page = Path(dest).read_text(encoding="utf-8")
        self.assertNotIn("<b>PROOF</b>", page)
        self.assertIn("&lt;b&gt;T&lt;/b&gt;", page)
        self.assertIn("\\u003c/script", page)

    def test_light_theme_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "b.html")
            board.main([DEMO, "--theme", "light", "--out", dest])
            self.assertEqual(page_data(dest)["theme"], "light")


class EndToEnd(unittest.TestCase):
    def test_demo_page_has_the_pieces(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "b.html")
            board.main([DEMO, "--out", dest])
            d = page_data(dest)
            page = Path(dest).read_text(encoding="utf-8")
        self.assertEqual(len(d["features"]), 3)
        self.assertEqual(d["score"], 3)
        self.assertEqual(d["max"], 4)
        self.assertIn("class=\"bar\"", page)
        self.assertIn("no person is named", page.lower())
        self.assertIn("over-determination", page.lower())


if __name__ == "__main__":
    unittest.main()