"""Render a generic, source-linked JSON network as a standalone HTML file."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit, unquote, quote

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SHAPES = {"dot", "square", "triangle", "diamond", "hexagon", "triangleDown", "ellipse", "box", "star"}


def safe_href(value):
    """Allow ordinary HTTPS/HTTP sources, fragments and portable relative links."""
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Source links must be nonempty text without control characters")
    parsed = urlsplit(value)
    if parsed.scheme:
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError("Source links require HTTP(S) without embedded credentials")
    elif value.startswith(("/", "\\")) or "\\" in value:
        raise ValueError("Local source links must be relative, with forward slashes")
    return value


def validate_structure(data):
    """Reject malformed UI inputs before they reach the browser or filesystem."""
    def obj(value, name):
        if not isinstance(value, dict):
            raise ValueError(f"{name} must be an object")
    def text(value, name):
        if not isinstance(value, str):
            raise ValueError(f"{name} must be text")
    def sequence(value, name):
        if not isinstance(value, list):
            raise ValueError(f"{name} must be a list")
    obj(data, "Graph")
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Graph must contain finite JSON values") from exc
    for name in ("types", "relations", "records"):
        obj(data.get(name), name)
        for key, value in data[name].items():
            if not isinstance(key, str) or not key or key in {"__proto__", "constructor", "prototype"}:
                raise ValueError(f"Invalid {name} ID")
            obj(value, name + " entry")
    if not data["types"]:
        raise ValueError("At least one node type is required")
    for name in ("nodes", "edges", "links"):
        sequence(data.get(name, []), name)
        for item in data.get(name, []):
            obj(item, name + " entry")
    for name in ("title", "handling", "scope_note", "subtitle", "identity_note", "footer_note"):
        if name in data:
            text(data[name], name)
    for name in ("nodes", "edges"):
        if name not in data:
            raise ValueError(f"Missing {name}")
        for item in data[name]:
            for key in (("id", "label", "kind") if name == "nodes" else ("id", "from", "to", "relation")):
                text(item.get(key), name + "." + key)
                if key != "label" and item[key] in {"__proto__", "constructor", "prototype"}:
                    raise ValueError("Reserved graph identifier")
            if "details" in item:
                text(item["details"], "details")
    if "primary_type" in data and (not isinstance(data["primary_type"], str) or data["primary_type"] not in data["types"]):
        raise ValueError("Unknown primary_type")
    for relation in data["relations"].values():
        if "default" in relation and not isinstance(relation["default"], bool):
            raise ValueError("Relation default must be boolean")
        if "description" in relation:
            text(relation["description"], "description")
    for record in data["records"].values():
        text(record.get("status"), "record status")
        for key in ("details",):
            if key in record:
                text(record[key], key)
        sequence(record.get("uncertainty", []), "uncertainty")
        for value in record.get("uncertainty", []):
            text(value, "uncertainty")
        sequence(record.get("sources", []), "sources")
        for source in record.get("sources", []):
            obj(source, "source")
            for key in ("label", "href", "locator", "quote"):
                if key in source:
                    text(source[key], key)
    for link in data.get("links", []):
        text(link.get("label"), "link label")
        safe_href(link.get("href"))
    for kind in data["types"].values():
        if "shape" in kind:
            text(kind["shape"], "shape")


def rebase_links(data, input_path, output_path):
    """Resolve local links from the input directory and verify companion files."""
    data = deepcopy(data)
    links = list(data.get("links", []))
    for record in data["records"].values():
        links.extend(record.get("sources", []))
    for link in links:
        href = link.get("href")
        if not href:
            continue
        safe_href(href)
        parsed = urlsplit(href)
        if parsed.scheme or not parsed.path:
            continue
        target = (input_path.parent / unquote(parsed.path)).resolve()
        if not target.is_file():
            raise ValueError("Relative source target is missing: " + parsed.path)
        relative = Path(os.path.relpath(target, output_path.parent.resolve())).as_posix()
        link["href"] = urlunsplit(("", "", quote(relative, safe="/"), parsed.query, parsed.fragment))
    return data


def prepare(data):
    """Validate explicit IDs/support and derive UI indexes; never infer edges."""
    validate_structure(data)
    graph = deepcopy(data)
    for key in ("title", "handling", "scope_note"):
        if not isinstance(graph.get(key), str) or not graph[key].strip():
            raise ValueError(f"Missing text: {key}")
    records = graph["records"]
    if not isinstance(records, dict):
        raise ValueError("records must be an ID-keyed object")
    for rid, record in records.items():
        if not isinstance(rid, str) or not rid or record.get("status") not in {"recorded", "review"}:
            raise ValueError("Each record needs a text ID and recorded/review status")
        if not isinstance(record.get("label"), str):
            raise ValueError("Each record needs a label")
        for source in record.get("sources", []):
            if source.get("href"):
                safe_href(source["href"])
        if not isinstance(record.get("fields", {}), dict):
            raise ValueError("Record fields must be an object")
    types, relations = graph["types"], graph["relations"]
    for kind in types.values():
        if kind.get("shape", "dot") not in SHAPES or not isinstance(kind.get("label"), str):
            raise ValueError("Unknown node shape or missing type label")
    for relation in relations.values():
        if not isinstance(relation.get("label"), str):
            raise ValueError("Each relation needs a label")
        relation.setdefault("default", True)
    for link in graph.get("links", []):
        safe_href(link["href"])
    nodes, edge_ids = {}, set()

    def support(item):
        ids = item.get("records", [])
        if not isinstance(ids, list) or any(not isinstance(rid, str) or rid not in records for rid in ids):
            raise ValueError("Unknown supporting record ID")
        return sorted(set(ids))

    for node in graph["nodes"]:
        nid = node["id"]
        if not isinstance(nid, str) or not nid or nid in nodes or node["kind"] not in types:
            raise ValueError("Duplicate/invalid node ID or unknown type")
        if not isinstance(node.get("label"), str):
            raise ValueError("Each node needs a text label")
        node["own_mentions"] = support(node)
        node["mentions"] = list(node["own_mentions"])
        nodes[nid] = node
    for edge in graph["edges"]:
        eid = edge["id"]
        if not isinstance(eid, str) or not eid or eid in edge_ids:
            raise ValueError("Duplicate/invalid edge ID")
        edge_ids.add(eid)
        if edge["from"] not in nodes or edge["to"] not in nodes or edge["relation"] not in relations:
            raise ValueError("Unknown edge endpoint or relation")
        edge["mentions"] = support(edge)
        if not edge["mentions"]:
            raise ValueError("Every edge needs at least one supporting record")
        if not isinstance(edge.get("directed", True), bool):
            raise ValueError("Edge directed must be boolean")
        for nid in (edge["from"], edge["to"]):
            nodes[nid]["mentions"].extend(edge["mentions"])
    for node in nodes.values():
        node["mentions"] = sorted(set(node["mentions"]))
        if not node["mentions"]:
            raise ValueError("Isolated nodes need a supporting record")
    graph["counts"] = {"nodes": len(nodes), "edges": len(edge_ids), "records": len(records),
                       "review_records": sum(r["status"] == "review" for r in records.values())}
    return graph


def render(data, output, library):
    graph = prepare(data)
    config = json.loads((ASSETS / "library.json").read_text(encoding="utf-8"))
    content = library.read_bytes()
    digest = base64.b64encode(hashlib.sha384(content).digest()).decode()
    if digest != config["vis_network_sha384"]:
        raise ValueError("vis-network library does not match the repository integrity pin")
    graph["renderer"] = {"library": "vis-network 9.1.6", "sha384": digest, "source": config["vis_network_url"]}
    packed = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    packed = packed.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    values = {"__NETWORK_CSS__": (ASSETS / "network.css").read_text(encoding="utf-8"),
              "__NETWORK_JS__": (ASSETS / "network.js").read_text(encoding="utf-8"),
              "__VIS_LIBRARY__": re.sub(r"//# sourceMappingURL=.*", "", content.decode("utf-8")),
              "__GRAPH_JSON__": packed}
    template = (ASSETS / "network.html").read_text(encoding="utf-8")
    # One pass: imported strings resembling template tokens remain literal data.
    html = re.sub("|".join(re.escape(k) for k in values), lambda m: values[m.group(0)], template)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(html.replace("\r\n", "\n"))
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--vis-js", type=Path, default=ASSETS / "vendor/vis-network.min.js")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".html":
        parser.error("Output must have an .html extension")
    if args.output.exists() or args.output.with_suffix(".graph.json").exists():
        parser.error("Output exists; choose a new edition or archive the previous complete set")
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        prepare(data)
        data = rebase_links(data, args.input, args.output)
        graph = render(data, args.output, args.vis_js)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.with_suffix(".graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(graph["counts"]))


if __name__ == "__main__":
    main()
