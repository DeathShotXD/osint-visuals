#!/usr/bin/env python3
"""Newsroom locator map: where is this place? A main map with the country highlighted, nearby cities, a scale bar and
an inset globe. Standard library only.

  locator.py --place "Beira, Mozambique" --title "Cyclone makes landfall near Beira"
  locator.py --lat 19.8333 --lon -155.0833 --label "Hilo" --title "..." --half-width 300

Map data: Natural Earth (public domain), downloaded once and cached in ~/.cache/osint-visuals.
Place names: OpenStreetMap's Nominatim, one request per place, cached; please don't loop it over long lists
(usage policy: https://operations.osmfoundation.org/policies/nominatim/ ; max 1 request per second).
"""
import argparse
import html
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "locator.html")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "osint-visuals")
UA = "osint-visuals/0.1 (open-source evidence graphics; https://github.com/Ghongha007/osint-visuals)"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"


def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return json.load(open(path, encoding="utf-8"))


def geocode(q):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "nominatim-" + "".join(c if c.isalnum() else "_" for c in q.lower())[:80] + ".json")
    if os.path.exists(key):
        return json.load(open(key))
    stamp = os.path.join(CACHE, ".nominatim-last")       # never more than one request a second, even across runs
    if os.path.exists(stamp):
        wait = 1.1 - (time.time() - os.path.getmtime(stamp))
        if wait > 0: time.sleep(wait)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    open(stamp, "w").close()
    json.dump(res, open(key, "w"))
    return res


def rings_of(geom):
    if geom["type"] == "Polygon": return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon": return geom["coordinates"]
    return []


def contains(poly, x, y):
    c = False
    for ring in poly[:1]:
        for i in range(len(ring)):
            (x1, y1), (x2, y2) = ring[i - 1][:2], ring[i][:2]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1: c = not c
    return c


def simplify(pts, tol):
    """Douglas-Peucker on [lon, lat] points."""
    if len(pts) < 4: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True; stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop(); ax, ay = pts[a]; bx, by = pts[b]; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1e-12
        best, bi = -1, -1
        for i in range(a + 1, b):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + bx * ay - by * ax) / L
            if d > best: best, bi = d, i
        if best > tol: keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def simplify_ring(ring, tol):
    """Simplify a closed ring: open it first (its two ends are the same point), then close it again."""
    if len(ring) < 5: return ring
    s = simplify(ring[:-1], tol)
    return ring if len(s) < 3 else s + [s[0]]


def bbox_hit(ring, box):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return not (max(xs) < box[0] or min(xs) > box[2] or max(ys) < box[1] or min(ys) > box[3])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--place", help="a place name to look up (Nominatim)")
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--label", help="text next to the marker (default: the place's short name)")
    ap.add_argument("--title", default=""); ap.add_argument("--subtitle", default="")
    ap.add_argument("--half-width", type=float, default=None, help="km from the point to the side of the main map (default: fits the country)")
    ap.add_argument("--source", default="", help="source for the story's facts, shown on the graphic (optional)")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    geo = None
    if a.lat is None or a.lon is None:
        if not a.place: sys.exit("give --place, or --lat and --lon")
        res = geocode(a.place)
        if not res: sys.exit(f"Nominatim found nothing for {a.place!r}; try a fuller name or give --lat/--lon")
        geo = res[0]; a.lat, a.lon = float(geo["lat"]), float(geo["lon"])
    label = a.label or (geo["name"] if geo and geo.get("name") else (a.place or "").split(",")[0]) or f"{a.lat:.3f}, {a.lon:.3f}"
    c50 = fetch(NE + "ne_50m_admin_0_countries.geojson", "ne_50m_admin_0_countries.geojson")
    c110 = fetch(NE + "ne_110m_admin_0_countries.geojson", "ne_110m_admin_0_countries.geojson")
    places = fetch(NE + "ne_50m_populated_places_simple.geojson", "ne_50m_populated_places_simple.geojson")
    home = None
    for f in c50["features"]:
        if any(contains(poly, a.lon, a.lat) for poly in rings_of(f["geometry"])):
            home = f; break
    if home is None and geo:                                  # at sea or on a coast: take the geocoder's country
        cc = (geo.get("address", {}).get("country_code") or "").upper()
        home = next((f for f in c50["features"] if f["properties"].get("ISO_A2_EH", f["properties"].get("ISO_A2")) == cc), None)
    if a.half_width:
        hw = a.half_width
    elif home:
        xs = [p[0] for poly in rings_of(home["geometry"]) for p in poly[0]]; ys = [p[1] for poly in rings_of(home["geometry"]) for p in poly[0]]
        kx = 111.32 * math.cos(math.radians(a.lat))
        hw = max(abs(max(xs) - a.lon) * kx, abs(min(xs) - a.lon) * kx, abs(max(ys) - a.lat) * 110.6, abs(min(ys) - a.lat) * 110.6) * 1.08
        hw = max(180, min(1600, hw))
    else:
        hw = 400
    dlon = hw * 2.2 / (111.32 * math.cos(math.radians(a.lat))); dlat = hw * 2.2 / 110.6     # room for any frame shape
    box = (a.lon - dlon, a.lat - dlat, a.lon + dlon, a.lat + dlat)
    tol = hw / 111 / 600
    hname = home["properties"].get("NAME") if home else None
    main_c = []
    for f in c50["features"]:
        polys = []
        for poly in rings_of(f["geometry"]):
            if bbox_hit(poly[0], box):
                polys.append([[[round(x, 3), round(y, 3)] for x, y in simplify_ring([p[:2] for p in poly[0]], tol)]])
        if polys:
            p = f["properties"]
            main_c.append({"n": p.get("NAME"), "home": p.get("NAME") == hname, "lx": p.get("LABEL_X"), "ly": p.get("LABEL_Y"), "polys": polys})
    globe = []
    for f in c110["features"]:
        polys = [[[[round(x, 1), round(y, 1)] for x, y in simplify_ring([p[:2] for p in poly[0]], 0.25)]] for poly in rings_of(f["geometry"])]
        globe.append({"home": f["properties"].get("NAME") == hname, "polys": polys})
    cities = []
    for f in places["features"]:
        p = f["properties"]; x, y = f["geometry"]["coordinates"][:2]
        if box[0] <= x <= box[2] and box[1] <= y <= box[3] and abs(x - a.lon) + abs(y - a.lat) > 0.05:
            cities.append({"n": p.get("name"), "x": round(x, 3), "y": round(y, 3), "pop": p.get("pop_max") or 0,
                           "cap": (p.get("featurecla") or "").startswith("Admin-0 capital"), "rank": p.get("scalerank", 9)})
    cities.sort(key=lambda c: (-c["cap"], -c["pop"]))
    data = {"title": a.title or f"{label}, {hname}" if hname else (a.title or label), "subtitle": a.subtitle, "label": label,
            "lat": a.lat, "lon": a.lon, "hw": hw, "country": hname, "countries": main_c, "globe": globe, "cities": cities[:40],
            "source": a.source, "geocoded": bool(geo), "theme": a.theme, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(data["title"]))
    dest = a.out or "locator-" + "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-") + ".html"
    open(dest, "w", encoding="utf-8").write(page)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {label} at {a.lat:.4f}, {a.lon:.4f}" + (f" (geocoded: {geo.get('display_name', '')[:90]})" if geo else ""))
    print(f"  country: {hname or 'none found (at sea?)'}; main map about {round(hw * 2)} km across; {len(cities)} nearby cities")
    if geo:
        print("  check the geocoded point is the place you mean; give --lat/--lon to override")
    return 0


if __name__ == "__main__":
    sys.exit(main())
