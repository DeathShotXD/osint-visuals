"""Offline tests for the ATT&CK coverage matrix. The demo counts are invented."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "attack", "demo-coverage.csv")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


attack = load("skills/attack-coverage/scripts/attack.py", "attack")


def page_data(path):
    s = open(path, encoding="utf-8").read()
    i = s.index("const D = ") + len("const D = ")
    return json.JSONDecoder().raw_decode(s[i:])[0]


class Build(unittest.TestCase):
    def setUp(self):
        self.data = attack.build(attack.load(DEMO))

    def test_totals_and_aggregation(self):
        self.assertEqual(self.data["technique_count"], 12)
        self.assertEqual(len(self.data["tactics"]), 12)
        self.assertEqual(self.data["total"], 24)
        self.assertEqual(self.data["max"], 4)
        ia = next(t for t in self.data["tactics"] if t["key"] == "initial-access")
        phishing = next(c for c in ia["techniques"] if c["id"] == "T1566")
        self.assertEqual(phishing["count"], 4)
        self.assertEqual(len(phishing["sources"]), 2)

    def test_canonical_tactic_order(self):
        keys = [t["key"] for t in self.data["tactics"]]
        self.assertEqual(keys[0], "initial-access")
        self.assertEqual(keys[1], "execution")
        self.assertEqual(keys[-1], "impact")

    def test_unknown_tactic_goes_last(self):
        rows = [{"tactic": "impact", "technique_id": "T1", "technique": "A", "count": "1"},
                {"tactic": "made-up", "technique_id": "T2", "technique": "B", "count": "1"}]
        data = attack.build(rows)
        self.assertEqual([t["key"] for t in data["tactics"]], ["impact", "made-up"])

    def test_notes_and_sources(self):
        t = next(t for t in self.data["tactics"] if t["key"] == "command-and-control")
        c = t["techniques"][0]
        self.assertEqual(c["id"], "T1071")
        self.assertEqual(c["count"], 4)


class Load(unittest.TestCase):
    def test_json_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rows.json")
            json.dump([{"tactic": "execution", "technique_id": "T1059", "technique": "Shell", "count": 2}], open(p, "w"))
            data = attack.build(attack.load(p))
            self.assertEqual(data["technique_count"], 1)
            self.assertEqual(data["total"], 2)

    def test_empty_csv_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "empty.csv")
            open(p, "w").write("tactic,technique_id,count\n")
            with self.assertRaises(SystemExit):
                attack.load(p)


class Page(unittest.TestCase):
    def test_page_written(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "m.html")
            attack.main([DEMO, "--title", "T", "--source", "S", "--out", dest])
            data = page_data(dest)
            self.assertEqual(data["technique_count"], 12)
            self.assertEqual(data["source"], "S")

    def test_input_cannot_close_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "rows.csv"), os.path.join(d, "m.html")
            open(src, "w").write("tactic,technique_id,technique,count\n"
                                 "execution,T1059,\"</script><b>PROOF</b>\",1\n")
            attack.main([src, "--out", dest])
            s = open(dest, encoding="utf-8").read()
            self.assertNotIn("<b>PROOF</b>", s)
            self.assertIn("\\u003c/script", s)


if __name__ == "__main__":
    unittest.main()