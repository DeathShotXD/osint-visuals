#!/usr/bin/env python3
"""Turn a conflict event table into an offline, aggregate-first graphic: where events happened, how they change over
time, and what kind they were.

Standard library only. It reads the CSV or JSON you downloaded, keeps the columns it recognises by name, and draws
one HTML page: a map of event points, a monthly chart of events and reported deaths, a type breakdown and a table.
Nothing is fetched. No victim names, no targeting: the graphic aggregates, and every export says where the data came
from and what it cannot show.

Recognised columns (UCDP GED names work as they are):
  date_start / date / year, latitude / lat, longitude / lon, best / high / deaths_civilians,
  type_of_violence / event_type, country, source_headline / source_office / source_article

    conflict.py events.csv --title "Conflict events, 2025" --source "UCDP GED 25.1, CC BY 4.0" --out conflict.html
"""
import argparse
import csv
import html
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "conflict.html")

NAMES = {
    "date": ["date_start", "date", "event_date", "start_date", "dtg"],
    "year": ["year", "active_year"],
    "lat": ["latitude", "lat", "y"],
    "lon": ["longitude", "lon", "lng", "x"],
    "deaths": ["best", "fatalities", "deaths", "deaths_total", "killed"],
    "high": ["high", "deaths_high"],
    "low": ["low", "deaths_low"],
    "civilians": ["deaths_civilians", "civilian_deaths"],
    "type": ["type_of_violence", "event_type", "violence_type", "type"],
    "country": ["country", "country_name", "location"],
    "source": ["source_headline", "source_office", "source_article", "source"],
}
TYPE_LABELS = {"1": "State-based conflict", "2": "Non-state conflict", "3": "One-sided violence"}
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "osint-visuals")
UA = "osint-visuals/0.3 (open-source evidence graphics; https://github.com/Ghongha007/osint-visuals)"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"


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


def simplify(pts, tol):
    """Douglas-Peucker, enough for a small background map."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1e-12
        best, bi = -1, -1
        for i in range(a + 1, b):
            if length < 1e-12:                     # a closed ring: the two ends are the same point
                d = math.hypot(pts[i][0] - ax, pts[i][1] - ay)
            else:
                d = abs(dy * pts[i][0] - dx * pts[i][1] + bx * ay - by * ax) / length
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def basemap(bbox=None):
    """Country outlines for the background. Natural Earth 110m, cached, simplified to the view; empty on failure."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "ne_110m_admin_0_countries.geojson")
    try:
        if not os.path.exists(path):
            req = urllib.request.Request(NE, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
        data = json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        print(f"note: no background map ({ex}); the points will be drawn on their own")
        return []
    # a regional view needs finer outlines than a world view
    span = (bbox[2] - bbox[0]) if bbox else 360
    tol = max(0.08, min(0.8, span / 40))
    view = None if bbox is None else (bbox[0] - span * 0.15, bbox[1] - span * 0.15,
                                      bbox[2] + span * 0.15, bbox[3] + span * 0.15)
    out = []
    for f in data.get("features", []):
        rings = []
        for ring in rings_of(f["geometry"]):
            pts = [[q[0], q[1]] for q in ring[0]]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                rings.append(pts)
        if not rings:
            continue
        lons = [p[0] for r in rings for p in r]
        lats = [p[1] for r in rings for p in r]
        if view and (max(lons) < view[0] or min(lons) > view[2] or max(lats) < view[1] or min(lats) > view[3]):
            continue
        polys = []
        for pts in rings:
            s2 = simplify(pts, tol)
            if len(s2) >= 3:
                polys.append([[round(p[0], 3), round(p[1], 3)] for p in s2])
        if polys:
            out.append(polys)
    return out


def load(path):
    if os.path.splitext(path)[1].lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("events") or data.get("rows") or data.get("data") or data.get("Result")
        if not isinstance(data, list):
            sys.exit(f"{path}: expected a list of events (or an object with events/rows/data/Result)")
        return data
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path}: no rows")
    return rows


def number(value, default=0.0):
    try:
        v = float(str(value).replace(",", "").strip())
        return v
    except (TypeError, ValueError):
        return default


def month_of(row, cdate, cyear):
    if cdate:
        v = str(row.get(cdate) or "").strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(v[:10], fmt).strftime("%Y-%m")
            except ValueError:
                continue
        if len(v) >= 7 and v[:4].isdigit():
            return v[:7]
    if cyear:
        v = str(row.get(cyear) or "").strip()
        if len(v) == 4 and v.isdigit():
            return v + "-01"
    return None


def parse(rows):
    if not rows:
        return [], {}
    header = list(rows[0].keys())
    cols = {k: pick(header, k) for k in NAMES}
    if not (cols["lat"] and cols["lon"]):
        sys.exit(f"need latitude and longitude columns; found {header}")
    if not (cols["date"] or cols["year"]):
        sys.exit(f"need a date_start/date or year column; found {header}")
    events, skipped = [], 0
    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        lat, lon = number(row.get(cols["lat"]), None), number(row.get(cols["lon"]), None)
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            skipped += 1
            continue
        month = month_of(row, cols["date"], cols["year"])
        if not month:
            skipped += 1
            continue
        deaths = number(row.get(cols["deaths"])) if cols["deaths"] else 0
        events.append({
            "lat": round(lat, 4), "lon": round(lon, 4), "month": month,
            "deaths": deaths, "high": number(row.get(cols["high"])) if cols["high"] else 0,
            "low": number(row.get(cols["low"])) if cols["low"] else 0,
            "civilians": number(row.get(cols["civilians"])) if cols["civilians"] else 0,
            "type": str(row.get(cols["type"]) or "").strip() if cols["type"] else "",
            "country": str(row.get(cols["country"]) or "").strip() if cols["country"] else "",
            "source": (str(row.get(cols["source"]) or "").strip() if cols["source"] else "")[:400],
        })
    return events, {"rows": len(rows), "skipped": skipped, "columns": {k: v for k, v in cols.items() if v}}


def aggregate(events):
    monthly, by_type, by_country = {}, {}, {}
    total_deaths = total_high = total_civ = 0
    for e in events:
        m = monthly.setdefault(e["month"], {"month": e["month"], "events": 0, "deaths": 0})
        m["events"] += 1
        m["deaths"] += e["deaths"]
        total_deaths += e["deaths"]
        total_high += e["high"]
        total_civ += e["civilians"]
        if e["type"]:
            t = by_type.setdefault(e["type"], {"key": e["type"], "label": TYPE_LABELS.get(e["type"], e["type"]),
                                               "events": 0, "deaths": 0})
            t["events"] += 1
            t["deaths"] += e["deaths"]
        if e["country"]:
            c = by_country.setdefault(e["country"], {"country": e["country"], "events": 0, "deaths": 0})
            c["events"] += 1
            c["deaths"] += e["deaths"]
    series = [monthly[k] for k in sorted(monthly)]
    months = [m["month"] for m in series]
    # fill gaps so the chart has a continuous axis
    filled = []
    if len(months) > 1:
        cur = datetime.strptime(months[0], "%Y-%m")
        last = datetime.strptime(months[-1], "%Y-%m")
        while cur <= last:
            key = cur.strftime("%Y-%m")
            filled.append(monthly.get(key, {"month": key, "events": 0, "deaths": 0}))
            cur = datetime(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    else:
        filled = series
    lats = [e["lat"] for e in events]
    lons = [e["lon"] for e in events]
    return {
        "total_events": len(events), "total_deaths": int(total_deaths), "total_high": int(total_high),
        "total_civilians": int(total_civ), "monthly": filled,
        "types": sorted(by_type.values(), key=lambda t: -t["events"]),
        "countries": sorted(by_country.values(), key=lambda c: -c["events"])[:12],
        "bbox": [min(lons), min(lats), max(lons), max(lats)] if events else None,
        "range": [months[0], months[-1]] if months else None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("--title", default="Conflict events")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="where the table came from, shown on the graphic")
    ap.add_argument("--from", dest="since", help="keep events from this YYYY-MM onward")
    ap.add_argument("--to", dest="until", help="keep events up to this YYYY-MM")
    ap.add_argument("--country", help="keep one country (exact match, case-insensitive)")
    ap.add_argument("--type", help="keep one type_of_violence code, e.g. 1, 2 or 3")
    ap.add_argument("--min-deaths", type=float, default=0, help="drop events below this reported death count")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--no-basemap", action="store_true", help="skip the Natural Earth country outlines")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    events, meta = parse(load(a.input))
    if a.since:
        events = [e for e in events if e["month"] >= a.since]
    if a.until:
        events = [e for e in events if e["month"] <= a.until]
    if a.country:
        c = a.country.lower()
        events = [e for e in events if e["country"].lower() == c]
    if a.type:
        events = [e for e in events if e["type"] == a.type]
    if a.min_deaths:
        events = [e for e in events if e["deaths"] >= a.min_deaths]
    if not events:
        sys.exit("no events left after filtering; check the date range, country, type and death threshold")
    data = aggregate(events)
    data["basemap"] = [] if a.no_basemap else basemap(data.get("bbox"))
    if len(events) > 4000:
        data["events"] = events[:4000]
        data["capped"] = True
    else:
        data["events"] = events
    data.update({"title": a.title, "subtitle": a.subtitle, "source": a.source, "theme": a.theme,
                 "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "input": os.path.basename(a.input), "meta": meta})
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or os.path.splitext(a.input)[0] + "-conflict.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {data['total_events']} events, {data['total_deaths']} reported deaths"
          + (f" (high estimate {data['total_high']})" if data["total_high"] else "")
          + f", {len(data['monthly'])} months, {meta['skipped']} rows skipped")
    if data["range"]:
        print(f"  range {data['range'][0]} to {data['range'][1]}")
    for t in data["types"]:
        print(f"    {t['label']}: {t['events']} events, {t['deaths']} deaths")
    if not a.source:
        print("note: no --source given; say where the table came from and when it was downloaded")
    print("  note: event data records reports, not verified facts. State the source, the period and the counts together.")
    return 0


if __name__ == "__main__":
    sys.exit(main())