"""Synthetic invariants for the reusable network renderer; no case data required."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
from copy import deepcopy
import unittest

import importlib.util

SKILL = Path(__file__).resolve().parents[1] / "skills/network-graph"
spec = importlib.util.spec_from_file_location("network", SKILL / "scripts/network.py")
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)
ASSETS, ROOT = network.ASSETS, network.ROOT
prepare, render, safe_href = network.prepare, network.render, network.safe_href


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ASSETS / "demo.json").read_text(encoding="utf-8"))

    def test_identity_and_support_preserved(self):
        self.data["nodes"][1]["label"] = self.data["nodes"][0]["label"]
        graph = prepare(self.data)
        self.assertEqual(graph["counts"]["nodes"], 6)
        self.assertEqual(graph["counts"]["edges"], 4)
        self.assertEqual(graph["nodes"][3]["mentions"], ["r1", "r2", "r3"])
        self.assertEqual(graph["edges"][3]["directed"], False)
        self.assertEqual(self.data["nodes"][3]["records"], [])
        self.assertNotIn("mentions", self.data["nodes"][3])

    def test_unknown_endpoints_and_support_rejected(self):
        for key, value in [("to", "missing"), ("relation", "missing"), ("records", ["missing"]), ("records", [])]:
            with self.subTest(key=key, value=value):
                source = json.loads(json.dumps(self.data))
                source["edges"][0][key] = value
                with self.assertRaises(ValueError):
                    prepare(source)

    def test_duplicate_ids_and_unsupported_isolate_rejected(self):
        self.data["nodes"][1]["id"] = self.data["nodes"][0]["id"]
        with self.assertRaises(ValueError):
            prepare(self.data)
        self.setUp()
        self.data["nodes"][-1]["records"] = []
        with self.assertRaises(ValueError):
            prepare(self.data)

    def test_safe_portable_links(self):
        for value in ["https://example.invalid/source", "../sources/record.json", "#section-1"]:
            self.assertEqual(safe_href(value), value)
        for value in ["javascript:alert(1)", "data:text/html,hello", "file:///private/source", "C:/private/source",
                      "//host/source", "/private/source", "https://user:secret@example.invalid", "https://@example.invalid", "http://:80", "a\nb", "https://example.invalid\\path", "https://example.invalid/\x7f"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_href(value)

    def test_literal_json_cannot_inject_or_replace_template(self):
        self.data["title"] = '</script><script>window.injected=true</script>__NETWORK_JS__\u2028'
        library = ASSETS / "vendor/vis-network.min.js"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "network.html"
            render(self.data, output, library)
            html = output.read_text(encoding="utf-8")
            packed = html.split('<script id="network-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            self.assertNotIn('</script', packed)
            self.assertEqual(json.loads(packed)["title"], self.data["title"])
            self.assertNotIn(b'\r\n', output.read_bytes())


    def test_duplicate_edges_and_malformed_input(self):
        cases = []
        d = deepcopy(self.data); d["edges"].append(deepcopy(d["edges"][0])); cases.append(d)
        d = deepcopy(self.data); d["edges"][0]["directed"] = "false"; cases.append(d)
        d = deepcopy(self.data); d["relations"]["membership"]["default"] = "false"; cases.append(d)
        d = deepcopy(self.data); d["nodes"][0]["id"] = "__proto__"; cases.append(d)
        d = deepcopy(self.data); d["records"]["r1"]["sources"] = {}; cases.append(d)
        d = deepcopy(self.data); d["records"]["r1"]["fields"] = {"bad": float("nan")}; cases.append(d)
        d = deepcopy(self.data); d["types"] = {}; cases.append(d)
        cases.extend([None, [], {}, {**self.data, "edges": [None]}])
        for data in cases:
            with self.subTest(data_type=type(data).__name__), self.assertRaises(ValueError):
                prepare(data)

    def test_deduplicated_support_and_sources_preserved(self):
        self.data["edges"][0]["records"] = ["r1", "r1", "r4"]
        graph = prepare(self.data)
        self.assertEqual(graph["edges"][0]["mentions"], ["r1", "r4"])
        self.assertEqual(graph["records"], self.data["records"])
        self.assertEqual(graph["nodes"][-1]["own_mentions"], ["r5"])

    def test_relative_source_rebasing_and_missing_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "input").mkdir(); (root / "out").mkdir()
            (root / "input/source note.txt").write_text("Fictional source")
            self.data["records"]["r1"]["sources"][0]["href"] = "source%20note.txt#section"
            graph = network.rebase_links(self.data, root / "input/graph.json", root / "out/graph.html")
            href = graph["records"]["r1"]["sources"][0]["href"]
            self.assertEqual(href, "../input/source%20note.txt#section")
            self.assertEqual(self.data["records"]["r1"]["sources"][0]["href"], "source%20note.txt#section")
            (root / "input/source note.txt").unlink()
            with self.assertRaises(ValueError):
                network.rebase_links(self.data, root / "input/graph.json", root / "out/graph.html")

    def test_portable_cli_and_existing_edition_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            import shutil
            root = Path(folder)
            shutil.copytree(SKILL, root / "skill", ignore=shutil.ignore_patterns("__pycache__"))
            command = [sys.executable, str(root / "skill/scripts/network.py"), "--input", str(root / "skill/assets/demo.json"), "--output", str(root / "demo.html")]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / "demo.graph.json").read_text(encoding="utf-8"))
            self.assertEqual(data["records"], self.data["records"])
            old = (root / "demo.html").read_bytes()
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "demo.html").read_bytes(), old)

    def test_library_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            lib = Path(folder) / "untrusted.js"
            lib.write_text("/* wrong library */")
            with self.assertRaises(ValueError):
                render(self.data, Path(folder) / "network.html", lib)

    def test_multilingual_data_round_trip(self):
        data = json.loads((ASSETS / "multilingual.json").read_text(encoding="utf-8"))
        data["nodes"][1]["id"] = "كيان-ألف"
        data["edges"][0]["from"] = "كيان-ألف"
        graph = prepare(data)
        self.assertEqual(graph["records"], data["records"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unicode.html"
            render(data, path, ASSETS / "vendor/vis-network.min.js")
            packed = path.read_text(encoding="utf-8").split('<script id="network-data" type="application/json">')[1].split('</script>')[0]
            decoded = json.loads(packed)
            self.assertEqual(decoded["records"], data["records"])
            self.assertEqual(decoded["nodes"][1]["id"], "كيان-ألف")
            for actual, original in zip(decoded["nodes"], data["nodes"]):
                self.assertEqual(actual["label"], original["label"])


if __name__ == "__main__":
    unittest.main()
