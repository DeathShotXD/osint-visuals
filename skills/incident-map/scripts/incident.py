#!/usr/bin/env python3
"""Draw an aggregate incident map from your own table: countries shaded by incident count, sectors and months
broken out, sources on the graphic.

Standard library only. One row per incident (or per already-aggregated country/sector/month, with a count column):

  date,country,sector,count,source
  2026-02-11,Germany,Manufacturing,2,Invented incident review Q1
  2026-03-02,Japan,Transport,1,Invented incident review Q1

The map is aggregate. The script reads country, sector, date and count, and deliberately ignores any column that
looks like an organisation or victim name: the graphic never names a victim, and the SKILL says why.

Country outlines: Natural Earth 110m, cached once and simplified to the view. No API key.
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
TEMPLATE = os.path.join(HERE, "..", "assets", "incident.html")

NAMES = {
    "date": ["date", "incident_date", "reported", "published", "month", "dtg"],
    "year": ["year", "active_year"],
    "country": ["country", "country_name", "iso", "iso2", "iso3", "country_code", "code", "nation"],
    "sector": ["sector", "industry", "victim_sector", "target_sector", "vertical", "segment"],
    "count": ["count", "incidents", "n", "value", "total"],
    "source": ["source", "reference", "report", "url", "source_url"],
}
IGNORED = ["organization", "organisation", "company", "victim", "entity", "target_name", "org", "customer",
           "domain", "hostname", "ip", "leak_site", "group_name"]
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
            if length < 1e-12:
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


def ne_data():
    """The cached Natural Earth file, or None when it cannot be read."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "ne_110m_admin_0_countries.geojson")
    try:
        if not os.path.exists(path):
            req = urllib.request.Request(NE, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
        return json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        print(f"note: no country outlines ({ex}); the map will be blank and the tables will still be right")
        return None


def country_index(data):
    """Map every sensible spelling of a country to the Natural Earth NAME.

    Three buckets, in rising priority: ISO codes, then a country's sovereign spelling, then its own name. A code is
    claimed by a sovereign over a dependency when the two collide, so FR stays France and does not become a
    territory. The ISO pass keeps Antarctica: only a real collision is resolved, not every "Antarctic" name.
    """
    names, sovereign, codes = {}, {}, {}
    for f in data.get("features", []):
        p = f.get("properties", {})
        name = p.get("NAME") or p.get("ADMIN")
        if not name:
            continue
        for key in ("NAME", "NAME_LONG", "ADMIN", "NAME_SORT"):
            v = p.get(key)
            if v and str(v) not in ("-99", ""):
                names.setdefault(str(v).strip().lower(), name)
        v = p.get("SOVEREIGNT")
        if v and str(v) not in ("-99", ""):
            sovereign.setdefault(str(v).strip().lower(), name)
        owns = p.get("SOVEREIGNT") == name      # a sovereign, not a dependency
        for key in ("ISO_A2", "ISO_A3", "ISO_A2_EH"):
            v = p.get(key)
            if v and str(v) not in ("-99", ""):
                k = str(v).strip().lower()
                if k not in codes or owns:
                    codes[k] = name
    lookup = dict(codes)
    lookup.update(sovereign)
    lookup.update(names)
    # a few ISO_A3 values are "-99" in Natural Earth 110m, so spell them out
    for code, name in (("fra", "France"), ("gbr", "United Kingdom"), ("usa", "United States of America"),
                       ("nor", "Norway"), ("swe", "Sweden")):
        if name in {v for v in names.values()}:
            lookup.setdefault(code, name)
    return lookup


def load(path):
    if os.path.splitext(path)[1].lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("incidents") or data.get("rows") or data.get("data")
        if not isinstance(data, list):
            sys.exit(f"{path}: expected a list of rows (or an object with incidents/rows/data)")
        return data
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path}: no rows")
    return rows


def number(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def month_of(row, cdate, cyear):
    for col in (cdate, cyear):
        if not col:
            continue
        v = str(row.get(col) or "").strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m"):
            try:
                return datetime.strptime(v[:10], fmt).strftime("%Y-%m")
            except ValueError:
                continue
        if len(v) >= 7 and v[:4].isdigit() and v[4] == "-":
            return v[:7]
        if len(v) == 4 and v.isdigit():
            return v + "-01"
    return None


def parse(rows, lookup):
    if not rows:
        return [], {}
    header = list(rows[0].keys())
    cols = {k: pick(header, k) for k in NAMES}
    ignored = [h for h in header if h.strip().lower() in IGNORED]
    if ignored:
        print("note: ignoring column(s) " + ", ".join(ignored) + ": this graphic never names organisations or victims")
    if not cols["country"]:
        sys.exit(f"need a country column; found {header}")
    if not (cols["date"] or cols["year"]):
        sys.exit(f"need a date or year column; found {header}")
    events, unmapped, skipped = [], set(), 0
    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        raw = str(row.get(cols["country"]) or "").strip()
        month = month_of(row, cols["date"], cols["year"])
        if not raw or not month:
            skipped += 1
            continue
        name = lookup.get(raw.lower()) or raw.strip()      # unknown spelling still counts, under its own name
        if raw.lower() not in lookup and lookup:
            unmapped.add(raw.strip())
        count = number(row.get(cols["count"])) if cols["count"] else 1
        if count <= 0:
            count = 1
        sector = (str(row.get(cols["sector"]) or "").strip() if cols["sector"] else "") or "Not stated"
        source = (str(row.get(cols["source"]) or "").strip() if cols["source"] else "")[:300]
        events.append({"m": month, "c": name, "s": sector, "n": count, "src": source})
    return events, {"rows": len(rows), "skipped": skipped, "unmapped": sorted(unmapped),
                    "columns": {k: v for k, v in cols.items() if v}, "ignored": ignored}


def view_countries(data, wanted, span_hint=None):
    """Simplified outlines for the countries in the view, keyed by Natural Earth NAME."""
    if data is None:
        return [], None
    feats = {}
    for f in data.get("features", []):
        name = f.get("properties", {}).get("NAME")
        if not name:
            continue
        rings = []
        for ring in rings_of(f["geometry"]):
            pts = [[q[0], q[1]] for q in ring[0]]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                rings.append(pts)
        if rings:
            feats[name] = rings
    if wanted:
        lons = [p[0] for n in wanted if n in feats for r in feats[n] for p in r]
        lats = [p[1] for n in wanted if n in feats for r in feats[n] for p in r]
    if not wanted or not lons:
        view = [-180, -60, 180, 75]
    else:
        padx = max(2.0, (max(lons) - min(lons)) * 0.25)
        pady = max(2.0, (max(lats) - min(lats)) * 0.25)
        view = [min(lons) - padx, min(lats) - pady, max(lons) + padx, max(lats) + pady]
    span = view[2] - view[0]
    tol = max(0.08, min(0.8, span / 45))
    out = []
    for name, rings in feats.items():
        lons = [p[0] for r in rings for p in r]
        lats = [p[1] for r in rings for p in r]
        if max(lons) < view[0] or min(lons) > view[2] or max(lats) < view[1] or min(lats) > view[3]:
            continue
        polys = []
        for r in rings:
            s = simplify(r, tol)
            if len(s) >= 3:
                polys.append([[round(p[0], 3), round(p[1], 3)] for p in s])
        if polys:
            out.append({"name": name, "polys": polys})
    return out, view


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("--title", default="Incidents by country")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="where the incidents came from, shown on the graphic")
    ap.add_argument("--from", dest="since", help="count incidents from this YYYY-MM onward")
    ap.add_argument("--to", dest="until", help="count incidents up to this YYYY-MM")
    ap.add_argument("--sector", action="append", default=[], help="keep only this sector (repeatable)")
    ap.add_argument("--min-count", type=float, default=0, help="drop rows whose count is below this")
    ap.add_argument("--no-basemap", action="store_true", help="skip the Natural Earth outlines")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    geo = None if a.no_basemap else ne_data()
    lookup = country_index(geo) if geo else {}
    rows = load(a.input)
    events, meta = parse(rows, lookup)
    if a.since:
        events = [e for e in events if e["m"] >= a.since]
    if a.until:
        events = [e for e in events if e["m"] <= a.until]
    if a.sector:
        keep = {s.strip().lower() for s in a.sector}
        events = [e for e in events if e["s"].strip().lower() in keep]
    if a.min_count:
        events = [e for e in events if e["n"] >= a.min_count]
    if not events:
        sys.exit("no incidents left after filtering; check the country spellings, the date range and the sector filter")
    by_country, by_sector, by_month, total = {}, {}, {}, 0
    for e in events:
        total += e["n"]
        by_country[e["c"]] = by_country.get(e["c"], 0) + e["n"]
        by_sector[e["s"]] = by_sector.get(e["s"], 0) + e["n"]
        m = by_month.setdefault(e["m"], {"month": e["m"], "count": 0})
        m["count"] += e["n"]
    months = sorted(by_month)
    series = []
    if months:
        cur, last = datetime.strptime(months[0], "%Y-%m"), datetime.strptime(months[-1], "%Y-%m")
        while cur <= last:
            key = cur.strftime("%Y-%m")
            series.append(by_month.get(key, {"month": key, "count": 0}))
            cur = datetime(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    countries, view = view_countries(geo, set(by_country), None) if not a.no_basemap else ([], None)
    data = {"title": a.title, "subtitle": a.subtitle, "source": a.source, "theme": a.theme,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "input": os.path.basename(a.input), "events": events, "total": int(total),
            "countries": [{"name": k, "count": v, "events": sum(1 for e in events if e["c"] == k)}
                          for k, v in sorted(by_country.items(), key=lambda kv: -kv[1])],
            "sectors": [{"name": k, "count": v} for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])],
            "monthly": series, "basemap": countries, "view": view,
            "unmapped": meta["unmapped"], "meta": meta,
            "range": [months[0], months[-1]] if months else None}
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or os.path.splitext(a.input)[0] + "-incidents.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {meta['rows']} rows, {len(events)} incidents, total count {int(total)}, "
          f"{len(by_country)} countries, {len(by_sector)} sectors, {len(series)} months")
    for c in data["countries"][:6]:
        print(f"    {c['name']}: {c['count']}")
    if meta["unmapped"]:
        print("  country spellings not in the outline set (shown in the tables, not on the map): " +
              ", ".join(meta["unmapped"][:6]))
    if meta["ignored"]:
        print("  ignored columns: " + ", ".join(meta["ignored"]))
    if not a.source:
        print("note: no --source given; say where the incidents came from")
    print("  note: this is an aggregate of reports. Counts depend on the dataset and the collection window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())