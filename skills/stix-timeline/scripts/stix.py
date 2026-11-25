#!/usr/bin/env python3
"""Turn a STIX 2.1 bundle into an offline cyber incident timeline, with sources and confidence visible.

Standard library only. Accepts a bundle as exported by MISP, OpenCTI or a hand-written analyst file:

  stix.py bundle.json --title "Campaign timeline" --source "MISP export, 2026-06-01" --out timeline.html

The graphic is one HTML file: lanes by object type, bars for objects with a start and an end, dots for single
dates, a details panel, filters, and PNG/SVG export. Nothing is fetched when the page is opened.

This is a presentation tool. It does not verify STIX content, resolve identities or score attribution.
"""
import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "timeline.html")

LANES = [
    ("actor", "Threat actors", "intrusion-set, threat-actor"),
    ("campaign", "Campaigns", "campaign"),
    ("infrastructure", "Infrastructure", "infrastructure"),
    ("malware", "Malware and tools", "malware, tool"),
    ("technique", "Techniques", "attack-pattern"),
    ("vulnerability", "Vulnerabilities", "vulnerability"),
    ("indicator", "Indicators", "indicator"),
    ("observation", "Observations", "observed-data"),
    ("report", "Reports", "report"),
    ("mitigation", "Mitigations", "course-of-action"),
]
LANE_OF = {}
for lane, _, types in LANES:
    for t in types.split(", "):
        LANE_OF[t.strip()] = lane
DATE_FIELDS = ("first_seen", "valid_from", "published", "created")


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def parse_time(value):
    if not value or not isinstance(value, str):
        return None
    v = value.strip().replace("Z", "+00:00")
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        try:
            d = datetime.strptime(v[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        objects = data.get("objects")
        if objects is None and data.get("type") == "bundle":
            sys.exit(f"{path}: bundle has no objects")
        objects = objects if isinstance(objects, list) else [data]
    elif isinstance(data, list):
        objects = data
    else:
        sys.exit(f"{path}: expected a STIX bundle object or a list of objects")
    return [o for o in objects if isinstance(o, dict)]


def name_of(obj):
    for k in ("name", "title", "value", "pattern"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return obj.get("id", "unnamed")


def sources_of(obj):
    out = []
    for ref in obj.get("external_references") or []:
        if not isinstance(ref, dict):
            continue
        label = ref.get("source_name") or ref.get("external_id") or "source"
        url = ref.get("url")
        if url and isinstance(url, str) and url.startswith(("http://", "https://")):
            out.append({"label": str(label), "url": url})
        else:
            out.append({"label": str(label), "url": ""})
    return out


def techniques_of(obj):
    out = []
    for phase in obj.get("kill_chain_phases") or []:
        if isinstance(phase, dict) and phase.get("phase_name"):
            out.append(str(phase["phase_name"]))
    return sorted(set(out))


def build(objects, min_confidence=0):
    by_id, events, skipped = {}, [], 0
    for obj in objects:
        if obj.get("type") == "relationship":
            continue
        oid = obj.get("id")
        if not oid:
            skipped += 1
            continue
        by_id[oid] = name_of(obj)
        lane = LANE_OF.get(obj.get("type"))
        start = next((parse_time(obj.get(f)) for f in DATE_FIELDS if parse_time(obj.get(f))), None)
        end = parse_time(obj.get("last_seen")) or parse_time(obj.get("valid_until"))
        if lane is None or start is None:
            skipped += 1
            continue
        conf = obj.get("confidence")
        conf = int(conf) if isinstance(conf, (int, float)) else 0
        if conf < min_confidence:
            skipped += 1
            continue
        event = {
            "id": oid, "lane": lane, "type": obj.get("type"), "name": name_of(obj),
            "start": start.isoformat(), "end": end.isoformat() if end and end >= start else None,
            "confidence": conf, "description": (obj.get("description") or "").strip()[:1200],
            "labels": [str(x) for x in (obj.get("labels") or [])][:8],
            "sources": sources_of(obj), "techniques": techniques_of(obj),
        }
        events.append(event)
    events.sort(key=lambda e: (e["start"], e["name"]))
    links = []
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        a, b = obj.get("source_ref"), obj.get("target_ref")
        if a in by_id and b in by_id:
            links.append({"from": by_id[a], "to": by_id[b],
                          "kind": obj.get("relationship_type") or "related-to"})
    counts = {lane: sum(1 for e in events if e["lane"] == lane) for lane, _, _ in LANES}
    times = [parse_time(e["start"]) for e in events if parse_time(e["start"])]
    times += [parse_time(e["end"]) for e in events if e.get("end") and parse_time(e["end"])]
    return {
        "events": events, "links": links, "counts": counts, "skipped": skipped,
        "range": [min(times).isoformat(), max(times).isoformat()] if times else None,
        "lanes": [{"key": k, "label": label, "types": types} for k, label, types in LANES],
        "types": sorted({e["type"] for e in events}),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("--title", default="Cyber incident timeline")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="where the bundle came from, shown on the graphic")
    ap.add_argument("--min-confidence", type=int, default=0, help="drop objects below this STIX confidence")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    objects = load(a.bundle)
    data = build(objects, a.min_confidence)
    if not data["events"]:
        sys.exit(f"{a.bundle}: no objects with a usable date and a known type; "
                 "check created/first_seen/valid_from/published fields")
    data.update({"title": a.title, "subtitle": a.subtitle, "source": a.source, "theme": a.theme,
                 "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "input": os.path.basename(a.bundle)})
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or os.path.splitext(a.bundle)[0] + "-timeline.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {len(data['events'])} objects on the timeline, {len(data['links'])} relationships, "
          f"{data['skipped']} skipped (no date, unknown type or below confidence)")
    if data["range"]:
        print(f"  range {data['range'][0][:10]} to {data['range'][1][:10]}")
    for lane, label, _ in LANES:
        if data["counts"][lane]:
            print(f"    {label}: {data['counts'][lane]}")
    if not a.source:
        print("note: no --source given; the graphic will say the source is not stated")
    return 0


if __name__ == "__main__":
    sys.exit(main())