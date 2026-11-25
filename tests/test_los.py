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

    def test_profiles_are_monotonic(self):
        _, rows = self.run_profile([wall(49, 51, 20.0)])
        ds = [r["d"] for r in rows]
        self.assertEqual(ds, sorted(ds))
        self.assertEqual(rows[0]["t"], 0)
        self.assertEqual(rows[-1]["t"], 1)


if __name__ == "__main__":
    unittest.main()