#!/usr/bin/env python3
"""Draw an ATT&CK coverage matrix from your own counts: tactic columns, technique cells, sources on the graphic.

Standard library only. Input is a CSV or a JSON list with one row per technique:

  tactic,technique_id,technique,count,source
  initial-access,T1566,Phishing,4,Incident review Q1
  execution,T1059,Command and Scripting Interpreter,3,Incident review Q1

The skill does not bundle the ATT&CK matrix. You supply the techniques you care about, so the graphic shows your
coverage question, not a generic poster. Technique IDs and names are MITRE ATT&CK; counts are yours.
"""
import argparse
import csv
import html
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "matrix.html")

TACTICS = [
    "reconnaissance", "resource-development", "initial-access", "execution", "persistence",
    "privilege-escalation", "defense-evasion", "credential-access", "discovery",
    "lateral-movement", "collection", "command-and-control", "exfiltration", "impact",
]
LABELS = {
    "reconnaissance": "Reconnaissance", "resource-development": "Resource Development",
    "initial-access": "Initial Access", "execution": "Execution", "persistence": "Persistence",
    "privilege-escalation": "Privilege Escalation", "defense-evasion": "Defense Evasion",
    "credential-access": "Credential Access", "discovery": "Discovery",
    "lateral-movement": "Lateral Movement", "collection": "Collection",
    "command-and-control": "Command and Control", "exfiltration": "Exfiltration", "impact": "Impact",
    "unmapped": "Unmapped",
}
NAMES = {
    "tactic": ["tactic", "phase", "kill_chain_phase", "kill chain phase"],
    "id": ["technique_id", "techniqueid", "technique id", "tid", "id"],
    "name": ["technique", "technique_name", "name", "label"],
    "count": ["count", "score", "observations", "n", "value"],
    "source": ["source", "reference", "report"],
    "note": ["note", "notes", "comment", "description"],
}


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def pick(header, kind):
    low = {h.strip().lower(): h for h in header}
    for n in NAMES[kind]:
        if n in low:
            return low[n]
    return None


def norm_tactic(value):
    v = (value or "").strip().lower()
    for ch in ("_", "/"):
        v = v.replace(ch, "-")
    v = "-".join(v.split())
    aliases = {"command-and-control": "command-and-control", "c2": "command-and-control",
               "command and control": "command-and-control", "privilege escalation": "privilege-escalation",
               "defense evasion": "defense-evasion", "credential access": "credential-access",
               "lateral movement": "lateral-movement", "initial access": "initial-access",
               "resource development": "resource-development", "privilege-escalation": "privilege-escalation"}
    return aliases.get(v, v) if v else "unmapped"


def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("techniques") or data.get("rows") or data.get("data")
        if not isinstance(data, list):
            sys.exit(f"{path}: expected a list of technique rows (or an object with techniques/rows/data)")
        return data
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path}: no rows")
    header = list(rows[0].keys())
    ct, cid, cn = pick(header, "tactic"), pick(header, "id"), pick(header, "name")
    cc, cs, cnote = pick(header, "count"), pick(header, "source"), pick(header, "note")
    if not (ct and (cid or cn)):
        sys.exit(f"{path}: need a tactic column and a technique_id or technique column; found {header}")
    out = []
    for r in rows:
        out.append({
            "tactic": r.get(ct, ""), "id": (r.get(cid, "") if cid else "").strip(),
            "name": (r.get(cn, "") if cn else "").strip(),
            "count": (r.get(cc, "0") if cc else "0").strip() or "0",
            "source": (r.get(cs, "") if cs else "").strip(),
            "note": (r.get(cnote, "") if cnote else "").strip(),
        })
    return out


def build(rows):
    groups, total, sources = {}, 0, []
    for r in rows:
        if not isinstance(r, dict):
            continue
        tid = str(r.get("technique_id") or r.get("id") or "").strip()
        name = str(r.get("technique") or r.get("name") or "").strip()
        if not tid and not name:
            continue
        try:
            n = float(str(r.get("count", 0)).replace(",", "").strip() or 0)
        except ValueError:
            n = 0
        n = int(n) if n == int(n) else n
        total += n
        tactic = norm_tactic(str(r.get("tactic") or ""))
        g = groups.setdefault(tactic, {})
        key = tid or name
        cell = g.setdefault(key, {"id": tid, "name": name, "count": 0, "sources": [], "notes": []})
        cell["count"] += n
        if not cell["name"] and name:
            cell["name"] = name
        src = str(r.get("source") or "").strip()
        if src and src not in cell["sources"]:
            cell["sources"].append(src)
            if src not in sources:
                sources.append(src)
        note = str(r.get("note") or "").strip()
        if note and note not in cell["notes"]:
            cell["notes"].append(note)
    order = {k: i for i, k in enumerate(TACTICS)}
    keys = sorted(groups, key=lambda k: (order.get(k, len(TACTICS)), k))
    tactics = []
    for k in keys:
        techs = sorted(groups[k].values(), key=lambda c: (-float(c["count"]), c["id"] or c["name"]))
        tactics.append({"key": k, "label": LABELS.get(k, k.replace("-", " ").title()), "techniques": techs})
    mx = max((float(c["count"]) for t in tactics for c in t["techniques"]), default=0)
    return {"tactics": tactics, "max": mx, "total": total, "sources": sources,
            "technique_count": sum(len(t["techniques"]) for t in tactics)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("--title", default="ATT&CK coverage")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="where the counts came from, shown on the graphic")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    rows = load(a.input)
    data = build(rows)
    if not data["tactics"]:
        sys.exit(f"{a.input}: no usable rows (need a tactic and a technique id or name)")
    data.update({"title": a.title, "subtitle": a.subtitle, "source": a.source, "theme": a.theme,
                 "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "input": os.path.basename(a.input)})
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or os.path.splitext(a.input)[0] + "-matrix.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {data['technique_count']} techniques across {len(data['tactics'])} tactics, total count {data['total']}")
    for t in data["tactics"]:
        print(f"    {t['label']}: {len(t['techniques'])}")
    if not a.source:
        print("note: no --source given; say where the counts came from")
    return 0


if __name__ == "__main__":
    sys.exit(main())