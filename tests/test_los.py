"""Offline tests for the line-of-sight prototype. No network: terrain and buildings are synthetic."""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


los = load("skills/scene-diorama/scripts/los.py", "los")
diorama = load("skills/scene-diorama/scripts/diorama.py", "diorama")


def wall(x0, x1, height, name="Wall"):
    return {"p": [(x0, -20), (x1, -20), (x1, 20), (x0, 20)], "h": height, "n": name}


class TerrainEncoding(unittest.TestCase):
    def test_rgb_roundtrip(self):
        for metres in (-20, 0, 10, 290, 8848):
            v = metres + 32768
            r, rest = divmod(v, 256)
            g, b = divmod(rest, 1)
            self.assertAlmostEqual(los.elevation_from_rgb(int(r), int(g), int(b)), metres, places=1)


class Geometry(unittest.TestCase):
    def test_inside(self):
        poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(los.inside(5, 5, poly))
        self.assertFalse(los.inside(15, 5, poly))
        self.assertFalse(los.inside(-1, 5, poly))


class Profile(unittest.TestCase):
    def run_profile(self, buildings, ground=lambda x, z: 0.0, eye=10.0, target=10.0):
        return los.profile((0, 0), (100, 0), eye, target, ground, buildings, step=1.0)

    def test_flat_ground_is_clear(self):
        dist, rows = self.run_profile([])
        self.assertAlmostEqual(dist, 100, places=6)
        self.assertTrue(los.summarise(rows)["clear"])

    def test_low_wall_is_clear(self):
        _, rows = self.run_profile([wall(49, 51, 1.0)])
        self.assertTrue(los.summarise(rows)["clear"])

    def test_wall_blocks(self):
        _, rows = self.run_profile([wall(49, 51, 20.0)])
        v = los.summarise(rows)
        self.assertFalse(v["clear"])
        self.assertAlmostEqual(v["first"]["d"], 50, delta=2)
        self.assertIn(v["first"]["building"], ("Wall", ""))

    def test_high_camera_clears_the_wall(self):
        _, rows = self.run_profile([wall(49, 51, 20.0)], eye=35.0)
        self.assertTrue(los.summarise(rows)["clear"])

    def test_terrain_hill_blocks(self):
        _, rows = self.run_profile([], ground=lambda x, z: 25.0 if 45 <= x <= 55 else 0.0)
        v = los.summarise(rows)
        self.assertFalse(v["clear"])
        self.assertAlmostEqual(v["first"]["d"], 45, delta=1)

    def test_ground_taper_is_not_an_obstruction(self):
        # eye above a ground-level target on a slope: the rising ground under the
        # line used to read as a blocker even though nothing stands on it.
        _, rows = self.run_profile([], ground=lambda x, z: 10.0 - 10.0 * (x / 100.0), eye=20.0, target=0.0)
        self.assertTrue(los.summarise(rows)["clear"])

    def test_ridge_still_blocks_a_line_coming_down_to_a_target(self):
        # the guard must only exempt bare ground, not a real rise in the terrain.
        ground = lambda x, z: 30.0 if 45 <= x <= 55 else 10.0 - 10.0 * (x / 100.0)
        _, rows = self.run_profile([], ground=ground, eye=20.0, target=0.0)
        v = los.summarise(rows)
        self.assertFalse(v["clear"])
        self.assertAlmostEqual(v["first"]["d"], 45, delta=1)

    def test_profiles_are_monotonic(self):
        _, rows = self.run_profile([wall(49, 51, 20.0)])
        ds = [r["d"] for r in rows]
        self.assertEqual(ds, sorted(ds))
        self.assertEqual(rows[0]["t"], 0)
        self.assertEqual(rows[-1]["t"], 1)


class LosFor(unittest.TestCase):
    """The helper diorama.py calls."""

    def test_clear_case_fields(self):
        out = los.los_for((0, 0), (100, 0), 1.7, 0.0, lambda x, z: 0.0, [], 2.0, 0.3)
        self.assertTrue(out["clear"])
        self.assertEqual(out["distance_m"], 100.0)
        self.assertEqual(out["eye_m"], 1.7)
        self.assertEqual(out["target_m"], 0.0)
        self.assertEqual(len(out["rows"]), 51)

    def test_blocked_case(self):
        out = los.los_for((0, 0), (100, 0), 1.7, 0.0, lambda x, z: 0.0, [wall(49, 51, 20.0)], 2.0, 0.3)
        self.assertFalse(out["clear"])
        self.assertAlmostEqual(out["block"]["d"], 50, delta=2)

    def test_target_height_lifts_the_line(self):
        low = los.los_for((0, 0), (100, 0), 1.7, 0.0, lambda x, z: 0.0, [wall(49, 51, 6.0)], 2.0, 0.3)
        high = los.los_for((0, 0), (100, 0), 1.7, 12.0, lambda x, z: 0.0, [wall(49, 51, 6.0)], 2.0, 0.3)
        self.assertFalse(low["clear"])
        self.assertTrue(high["clear"])


class DioramaFlag(unittest.TestCase):
    def test_los_needs_camera_and_target(self):
        # exits before any Overpass request, so this stays offline
        with self.assertRaises(SystemExit):
            diorama.main(["--lat", "46.05", "--lon", "14.5", "--los", "--out", "/tmp/should-not-exist.html"])


if __name__ == "__main__":
    unittest.main()