"""Offline interaction review of the generic synthetic network fixture."""
import argparse
import json
import importlib.util
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def review(html, output):
    output.mkdir(parents=True, exist_ok=True)
    errors, warnings, remote = [], [], []
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1,
                                      accept_downloads=True)
        context.set_offline(True)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: warnings.append(m.text) if m.type in ("error", "warning") else None)
        page.on("request", lambda r: remote.append(r.url) if r.url.startswith(("http:", "https:")) else None)
        page.goto(html.resolve().as_uri(), wait_until="load", timeout=90000)
        page.wait_for_function("window.networkViewer && window.networkViewer.state.visibleNodes.length > 0", timeout=60000)
        page.locator("#physics").uncheck()
        page.wait_for_timeout(500)
        assert page.evaluate("window.networkViewer.exportView().physics.enabled") is False
        results["initial_visible"] = page.evaluate("({nodes:networkViewer.state.visibleNodes.length,edges:networkViewer.state.visibleEdges.length})")
        page.screenshot(path=str(output / "desktop.png"), full_page=True)

        page.locator("#allConnections").click()
        actual = page.evaluate("({nodes:networkViewer.state.visibleNodes.length,edges:networkViewer.state.visibleEdges.length})")
        expected = page.evaluate("({nodes:networkViewer.data.counts.nodes,edges:networkViewer.data.counts.edges})")
        assert actual == expected
        results["all_connections"] = actual
        page.locator("#includeReview").uncheck()
        assert page.evaluate("networkViewer.state.visibleEdges.every(e=>e.active.every(id=>networkViewer.data.records[id].status!=='review'))")
        assert page.evaluate("!networkViewer.state.visibleEdges.some(e=>e.id==='e4')")
        assert page.locator("#inspector").inner_text()
        page.locator("#includeReview").check()
        page.evaluate("networkViewer.selectEdge('e4')")
        assert "Undirected connection" in page.locator("#inspector").inner_text()
        assert page.evaluate("networkViewer.network.body.data.edges.get('e4').arrows.to.enabled") is False
        results["review_filter_and_undirected_link"] = "passed"
        page.locator("#resetFilters").click()
        target = page.evaluate("networkViewer.data.nodes.find(n=>n.id==='alpha')")
        assert target
        needle = target["label"]
        page.locator("#search").fill(needle)
        assert page.locator("#searchResults button").count() > 0
        page.locator("#search").press("Enter")
        assert page.evaluate("networkViewer.state.selected")
        page.locator("#focusDepth").select_option("1")
        page.wait_for_timeout(500)
        assert page.evaluate("networkViewer.state.visibleNodes.length") < expected["nodes"]
        page.locator("#inspector details").first.locator("summary").click()
        page.locator("#inspector blockquote").first.wait_for(state="visible")
        results["search_neighbourhood_evidence"] = "passed"
        page.wait_for_timeout(500)
        page.screenshot(path=str(output / "selected.png"), full_page=True)

        # Move a real node with pointer events while physics is paused.
        page.evaluate("networkViewer.network.focus(networkViewer.state.selected,{scale:1.2,animation:false})")
        point = page.evaluate("networkViewer.network.canvasToDOM(networkViewer.network.getPositions([networkViewer.state.selected])[networkViewer.state.selected])")
        before = page.evaluate("networkViewer.network.getPositions([networkViewer.state.selected])[networkViewer.state.selected]")
        rect = page.locator("#graph").bounding_box()
        page.mouse.move(rect["x"] + point["x"], rect["y"] + point["y"])
        page.mouse.down()
        page.mouse.move(rect["x"] + point["x"] + 60, rect["y"] + point["y"] + 30, steps=12)
        page.mouse.up()
        after = page.evaluate("networkViewer.network.getPositions([networkViewer.state.selected])[networkViewer.state.selected]")
        assert abs(after["x"] - before["x"]) + abs(after["y"] - before["y"]) > 5
        page.locator("#pinSelected").click()
        assert page.evaluate("networkViewer.exportView().pinned_nodes.includes(networkViewer.state.selected)")
        results["drag_and_pin"] = "passed"

        page.locator("#repulsion").fill("6000")
        page.locator("#repulsion").dispatch_event("input")
        page.locator("#damping").fill("0.35")
        page.locator("#damping").dispatch_event("input")
        page.locator("#reheat").click()
        assert page.evaluate("networkViewer.exportView().physics.enabled") is True
        page.locator("#physics").uncheck()
        assert page.evaluate("networkViewer.exportView().physics.repulsion") == 6000
        results["physics_controls"] = "passed"
        page.locator("#spring").fill("200")
        page.locator("#spring").dispatch_event("input")
        assert page.evaluate("networkViewer.exportView().physics.springLength") == 200
        page.locator("#showLabels").uncheck()
        assert page.evaluate("networkViewer.network.body.data.nodes.get().every(n=>n.label==='')")
        page.locator("#showLabels").check()
        page.locator("#focusDepth").select_option("2")
        assert page.evaluate("networkViewer.state.visibleNodes.length") >= 3
        page.locator("#focusDepth").select_option("1")
        page.locator("#fit").click()
        page.locator("#tableTab").click()
        assert page.locator("#edgeRows tr").count() > 0
        page.locator("#edgeRows tr").first.locator("button").nth(1).click()
        assert page.evaluate("networkViewer.state.selectedEdge")
        results["connection_table"] = "passed"
        page.locator("#graphTab").click()

        page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('test denial'))},configurable:true})")
        page.locator("#copyView").click()
        assert page.locator("#exportPanel").is_visible()
        export = json.loads(page.locator("#exportText").input_value())
        assert export["physics"]["repulsion"] == 6000
        assert export["physics"]["damping"] == .35
        assert export["pinned_nodes"]
        assert export["filters"]["focusDepth"] == 1
        page.locator("#closeExport").click()
        with page.expect_download() as download:
            page.locator("#downloadView").click()
        download.value.save_as(output / "exported_view.json")
        saved = json.loads((output / "exported_view.json").read_text(encoding="utf-8"))
        assert saved["physics"] == export["physics"]
        assert saved["pinned_nodes"] == export["pinned_nodes"]
        results["changed_state_export_and_clipboard_fallback"] = "passed"
        assert saved["positions"]
        with page.expect_download() as download:
            page.locator("#exportPNG").click()
        download.value.save_as(output / "network.png")
        assert (output / "network.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        results["png_export"] = "passed"
        page.locator("#allConnections").click()
        page.locator("#tableTab").click()
        page.locator("#edgeRows tr button").first.focus()
        page.keyboard.press("Enter")
        assert page.evaluate("networkViewer.state.selected")
        results["keyboard_table_inspection"] = "passed"
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        page.emulate_media(media="print")
        assert page.locator("#tablePanel").is_visible()
        assert not page.locator("#graph").is_visible()
        page.screenshot(path=str(output / "print.png"), full_page=True)
        results["print_alternative"] = "passed"
        context.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile.set_offline(True)
        narrow = mobile.new_page()
        narrow.on("pageerror", lambda e: errors.append(str(e)))
        narrow.on("request", lambda r: remote.append(r.url) if r.url.startswith(("http:", "https:")) else None)
        narrow.goto(html.resolve().as_uri(), wait_until="load", timeout=90000)
        narrow.wait_for_function("window.networkViewer && window.networkViewer.state.visibleNodes.length > 0", timeout=60000)
        assert narrow.locator("#controlDetails").evaluate("e=>e.open") is False
        assert narrow.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        narrow.screenshot(path=str(output / "mobile.png"), full_page=True)
        results["mobile_width_and_controls"] = "passed"
        mobile.close()

        # Exercise imported text through the actual browser and graph library.
        skill = Path(__file__).resolve().parents[1] / "skills/html-network-visualisation"
        spec = importlib.util.spec_from_file_location("network", skill / "scripts/network.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        fixture = json.loads((skill / "assets/demo.json").read_text(encoding="utf-8"))
        payload = '</script><img src="https://example.invalid/x" onerror="window.injected=true">__NETWORK_JS__'
        fixture["title"] = payload
        fixture["nodes"][0]["label"] = payload
        fixture["nodes"][1]["label"] = payload
        fixture["records"]["r1"]["sources"][0]["quote"] = payload
        fixture["edges"][0]["records"] = ["r1", "r4"]
        with tempfile.TemporaryDirectory() as folder:
            probe = Path(folder) / "inert.html"
            renderer.render(fixture, probe, skill / "assets/vendor/vis-network.min.js")
            check_context = browser.new_context()
            check_context.set_offline(True)
            check = check_context.new_page()
            check.on("pageerror", lambda e: errors.append(str(e)))
            check.on("request", lambda r: remote.append(r.url) if r.url.startswith(("http:", "https:")) else None)
            check.goto(probe.as_uri())
            check.wait_for_function("window.networkViewer")
            assert check.locator("#networkTitle").inner_text() == payload
            assert not check.evaluate("Boolean(window.injected)")
            assert check.locator("img").count() == 0
            check.evaluate("networkViewer.selectNode('alpha')")
            check.locator("#inspector details").first.locator("summary").click()
            assert check.locator("#inspector blockquote").first.inner_text() == payload
            check.locator("#search").fill(payload)
            assert check.locator("#searchResults button").count() == 2
            check.locator("#search").fill("")
            check.evaluate("networkViewer.selectEdge('e1')")
            assert check.evaluate("networkViewer.network.body.data.edges.get('e1').dashes.length>0")
            check.locator("#includeReview").uncheck()
            assert check.evaluate("networkViewer.network.body.data.edges.get('e1').dashes") is False
            assert "Needs review" not in check.locator("#inspector").inner_text()
            check_context.close()
        results["inert_text_ambiguous_labels_and_mixed_support"] = "passed"
        multilingual=json.loads((skill / "assets/multilingual.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            probe=Path(folder) / "multilingual.html"
            renderer.render(multilingual,probe,skill / "assets/vendor/vis-network.min.js")
            language_context=browser.new_context(viewport={"width":1600,"height":1000},accept_downloads=True)
            language_context.set_offline(True)
            page=language_context.new_page()
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.on("request",lambda r:remote.append(r.url) if r.url.startswith(("http:","https:")) else None)
            page.goto(probe.as_uri())
            page.wait_for_function("window.networkViewer")
            page.locator("#physics").uncheck()
            for node in multilingual["nodes"][1:]:
                page.locator("#search").fill(node["label"])
                assert page.locator("#searchResults button").first.inner_text().startswith(node["label"])
                page.locator("#search").press("Enter")
                assert page.evaluate("networkViewer.state.selected")==node["id"]
                assert page.locator("#inspector h2").inner_text()==node["label"]
                page.locator("#inspector details").first.locator("summary").click()
                assert page.locator("#inspector blockquote").first.inner_text()==multilingual["records"][node["id"]]["sources"][0]["quote"]
                if node["id"] in ("arabic","hebrew","mixed"):
                    assert page.locator("#inspector h2").evaluate("e=>getComputedStyle(e).direction")=="rtl"
            for query in ("ETOILE","E\u0301toile"):
                page.locator("#search").fill(query)
                page.locator("#search").press("Enter")
                assert page.evaluate("networkViewer.state.selected")=="accents"
            page.evaluate("networkViewer.selectNode('arabic')")
            page.locator("#inspector details").first.locator("summary").click()
            page.locator("#fit").click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(output / "multilingual.png"),full_page=True)
            with page.expect_download() as download:
                page.locator("#exportPNG").click()
            download.value.save_as(output / "multilingual-export.png")
            page.locator("#tableTab").click()
            assert multilingual["nodes"][1]["label"] in page.locator("#edgeRows").inner_text()
            page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
            page.emulate_media(media="print")
            page.screenshot(path=str(output / "multilingual-print.png"),full_page=True)
            language_context.close()
        results["multilingual_labels_search_sources_rtl_table_print_png"]="passed"
        browser.close()
    assert not errors, errors
    assert not warnings, warnings
    assert not remote, "External request attempted"
    results.update({"browser_errors": [], "browser_warnings": [], "external_requests": 0,
                    "offline_file_open": "passed", "screenshots": ["desktop.png", "selected.png", "mobile.png", "print.png", "network.png", "multilingual.png", "multilingual-export.png", "multilingual-print.png"]})
    (output / "browser_checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.html, args.output)
