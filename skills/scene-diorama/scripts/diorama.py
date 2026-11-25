#!/usr/bin/env python3
"""Build a 3D miniature of a real place, with the evidence placed on it: where a camera stood, what it could see,
and where the event was. Standard library only; map data from OpenStreetMap through the Overpass API.

  diorama.py --lat 46.0514 --lon 14.5061 --radius 110 --camera 46.05192,14.50525 --camera-bearing 125 \\
             --camera-height 9 --fov 60 --target 46.05135,14.50618 --target-label "Crowd gathers here" \\
             --title "Where the video was filmed from" --place "Ljubljana, Slovenia" --source "invented demo"

Writes ONE html page (three.js, orbit / isometric / camera's-eye views, PNG and WebM export).
Overpass is a shared, free service: this script makes one request per place and caches it
(~/.cache/osint-visuals). Please keep it that way: no loops over many places. Map data © OpenStreetMap
contributors, available under the Open Database Licence (ODbL).
"""
import argparse
import hashlib
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
TEMPLATE = os.path.join(HERE, "..", "assets", "diorama.html")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "osint-visuals")
UA = "osint-visuals/0.1 (open-source evidence graphics; https://github.com/Ghongha007/osint-visuals)"
OVERPASS = "https://overpass-api.de/api/interpreter"


def overpass(s, w, n, e):
    q = f"""[out:json][timeout:60];
(
  way["building"]({s},{w},{n},{e}); relation["building"]({s},{w},{n},{e});
  way["building:part"]({s},{w},{n},{e});
  way["highway"]({s},{w},{n},{e});
  way["railway"~"rail|tram|light_rail|subway"]({s},{w},{n},{e});
  way["waterway"]({s},{w},{n},{e}); way["natural"="water"]({s},{w},{n},{e}); relation["natural"="water"]({s},{w},{n},{e});
  way["leisure"~"park|garden|pitch|playground"]({s},{w},{n},{e});
  way["landuse"~"grass|forest|meadow|recreation_ground|village_green|cemetery"]({s},{w},{n},{e});
  way["natural"~"wood|scrub|grassland|beach|sand"]({s},{w},{n},{e});
  way["man_made"="bridge"]({s},{w},{n},{e}); way["amenity"="parking"]({s},{w},{n},{e});
  node["natural"="tree"]({s},{w},{n},{e});
);
out geom;"""
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "overpass-" + hashlib.sha1(q.encode()).hexdigest()[:16] + ".json")
    if os.path.exists(key):
        return json.load(open(key)), True
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            json.dump(data, open(key, "w"))
            return data, False
        except Exception as ex:                      # 429/504 mean the shared server is busy: wait, then stop
            if attempt == 2:
                sys.exit(f"Overpass request failed ({ex}). The public server may be busy; try again in a few minutes.")
            time.sleep(15 * (attempt + 1))


def project(lat0, lon0):
    kx = 111320 * math.cos(math.radians(lat0)); kz = 110540
    return lambda la, lo: (round((lo - lon0) * kx, 2), round(-(la - lat0) * kz, 2))   # x east, z south (three.js)


def clip_poly(pts, r):
    """Sutherland-Hodgman: clip a polygon to the square |x|,|z| <= r."""
    def clip(ps, inside, cross):
        out = []
        for i, p in enumerate(ps):
            q = ps[i - 1]
            if inside(p):
                if not inside(q): out.append(cross(q, p))
                out.append(p)
            elif inside(q):
                out.append(cross(q, p))
        return out
    for axis, sign in ((0, 1), (0, -1), (1, 1), (1, -1)):
        if not pts: break
        ins = lambda p, a=axis, s=sign: p[a] * s <= r
        def cx(a, b, ax=axis, s=sign):
            t = (s * r - a[ax]) / ((b[ax] - a[ax]) or 1e-9)
            return (round(a[0] + (b[0] - a[0]) * t, 2), round(a[1] + (b[1] - a[1]) * t, 2))
        pts = clip(pts, ins, cx)
    return pts


def clip_line(pts, r):
    """Cut a polyline to the square, keeping the pieces inside."""
    pieces, cur = [], []
    for a, b in zip(pts, pts[1:]):
        t0, t1, dx, dz = 0.0, 1.0, b[0] - a[0], b[1] - a[1]
        ok = True
        for p, q in ((-dx, a[0] + r), (dx, r - a[0]), (-dz, a[1] + r), (dz, r - a[1])):
            if p == 0:
                if q < 0: ok = False; break
            else:
                t = q / p
                if p < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(cur) > 1: pieces.append(cur)
            cur = []; continue
        A = (round(a[0] + dx * t0, 2), round(a[1] + dz * t0, 2)); B = (round(a[0] + dx * t1, 2), round(a[1] + dz * t1, 2))
        if not cur: cur = [A]
        cur.append(B)
        if t1 < 1:
            pieces.append(cur); cur = []
    if len(cur) > 1: pieces.append(cur)
    return pieces


def join_rings(parts):
    """Join the open pieces of a multipolygon's outer edge into closed rings (end to end, flipping pieces as needed)."""
    parts = [list(p) for p in parts if len(p) > 1]; rings = []
    while parts:
        ring = parts.pop(0)
        while ring[0] != ring[-1]:
            for i, p in enumerate(parts):
                if p[0] == ring[-1]: ring += p[1:]; break
                if p[-1] == ring[-1]: ring += p[-2::-1]; break
                if p[-1] == ring[0]: ring = p[:-1] + ring; break
                if p[0] == ring[0]: ring = p[:0:-1] + ring; break
            else:
                break                                  # the rest of the edge is outside what was downloaded
            parts.pop(i)
        if len(ring) > 3:
            rings.append(ring if ring[0] == ring[-1] else ring + [ring[0]])
    return rings


def height_of(tags):
    for k in ("height", "building:height"):
        v = tags.get(k)
        if v:
            try: return max(2.5, float(v.replace("m", "").strip().split(";")[0]))
            except ValueError: pass
    lv = tags.get("building:levels")
    if lv:
        try: return float(lv.split(";")[0]) * 3.2 + 1.2
        except ValueError: pass
    return {"house": 7, "detached": 7, "residential": 11, "apartments": 15, "commercial": 13, "retail": 9, "office": 18,
            "church": 18, "cathedral": 26, "garage": 3.2, "shed": 3, "roof": 4, "industrial": 9, "warehouse": 10}.get(tags.get("building"), 10)


ROAD_W = {"motorway": 14, "trunk": 13, "primary": 11, "secondary": 10, "tertiary": 9, "residential": 7, "unclassified": 7,
          "living_street": 6, "service": 4.5, "pedestrian": 8, "footway": 2.4, "path": 2, "cycleway": 2.4, "steps": 2.4, "track": 3}


def build(data, P, r):
    out = {"buildings": [], "roads": [], "water": [], "green": [], "rails": [], "trees": [], "paved": []}
    for el in data.get("elements", []):
        t = el.get("tags", {})
        if el["type"] == "node":
            if t.get("natural") == "tree":
                x, z = P(el["lat"], el["lon"])
                if abs(x) <= r and abs(z) <= r: out["trees"].append([x, z])
            continue
        rings = []
        if el["type"] == "way" and "geometry" in el:
            rings = [[P(g["lat"], g["lon"]) for g in el["geometry"]]]
        elif el["type"] == "relation":
            rings = join_rings([[P(g["lat"], g["lon"]) for g in m["geometry"]] for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m])
        for ring in rings:
            closed = len(ring) > 3 and ring[0] == ring[-1]
            if "building" in t or "building:part" in t:
                if not closed: continue
                poly = clip_poly(ring[:-1], r)
                if len(poly) >= 3:
                    out["buildings"].append({"p": poly, "h": round(height_of(t), 1), "min": float(t.get("min_height", 0) or 0) if str(t.get("min_height", "0")).replace(".", "").isdigit() else 0,
                                             "k": t.get("building") or t.get("building:part") or "yes", "n": t.get("name", "")})
            elif t.get("natural") == "water" or (t.get("waterway") in ("riverbank", "dock")):
                poly = clip_poly(ring[:-1], r) if closed else []
                if len(poly) >= 3: out["water"].append(poly)
            elif "waterway" in t:
                for piece in clip_line(ring, r): out["roads"].append({"p": piece, "w": 6 if t["waterway"] in ("river", "canal") else 2.5, "k": "water"})
            elif "highway" in t:
                if closed and t.get("area") == "yes":
                    poly = clip_poly(ring[:-1], r)
                    if len(poly) >= 3: out["paved"].append(poly)
                    continue
                for piece in clip_line(ring, r): out["roads"].append({"p": piece, "w": ROAD_W.get(t["highway"], 5), "k": t["highway"]})
            elif "railway" in t:
                for piece in clip_line(ring, r): out["rails"].append(piece)
            elif closed and (t.get("amenity") == "parking" or t.get("man_made") == "bridge"):
                poly = clip_poly(ring[:-1], r)
                if len(poly) >= 3: out["paved"].append(poly)
            elif closed:
                poly = clip_poly(ring[:-1], r)
                if len(poly) >= 3: out["green"].append(poly)
    return out


def point(s, P):
    la, lo = map(float, s.split(","))
    return P(la, lo)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=120, help="half the side of the square, metres (60-250)")
    ap.add_argument("--camera", help="LAT,LON where the photo or video was taken from")
    ap.add_argument("--camera-bearing", type=float, help="direction the camera faced, degrees from north")
    ap.add_argument("--camera-height", type=float, default=1.7, help="metres above the ground (a balcony, a roof...)")
    ap.add_argument("--fov", type=float, default=60, help="horizontal field of view in degrees (phone main camera ~ 65-75)")
    ap.add_argument("--target", help="LAT,LON of what the camera shows (the event)")
    ap.add_argument("--target-label", default="")
    ap.add_argument("--label", action="append", default=[], help='extra marker "LAT,LON,text" (repeatable)')
    ap.add_argument("--title", default="The scene"); ap.add_argument("--place", default=""); ap.add_argument("--source", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    r = max(60, min(250, a.radius)); P = project(a.lat, a.lon)
    dlat = (r * 1.25) / 110540; dlon = (r * 1.25) / (111320 * math.cos(math.radians(a.lat)))
    osm, cached = overpass(round(a.lat - dlat, 6), round(a.lon - dlon, 6), round(a.lat + dlat, 6), round(a.lon + dlon, 6))
    scene = build(osm, P, r)
    ev = {}
    if a.camera:
        x, z = point(a.camera, P); ev["camera"] = {"x": x, "z": z, "h": a.camera_height, "bearing": a.camera_bearing, "fov": a.fov}
    if a.target:
        x, z = point(a.target, P); ev["target"] = {"x": x, "z": z, "label": a.target_label}
        if a.camera and a.camera_bearing is None:          # face the target if no bearing was given
            c = ev["camera"]; ev["camera"]["bearing"] = round(math.degrees(math.atan2(x - c["x"], -(z - c["z"]))) % 360, 1)
    if a.camera and a.target:
        c, t = ev["camera"], ev["target"]; ev["distance_m"] = round(math.hypot(t["x"] - c["x"], t["z"] - c["z"]))
    ev["labels"] = []
    for s in a.label:
        la, lo, text = s.split(",", 2); x, z = P(float(la), float(lo)); ev["labels"].append({"x": x, "z": z, "text": text.strip()})
    data = {"title": a.title, "place": a.place, "source": a.source, "lat": a.lat, "lon": a.lon, "r": r, "scene": scene, "evidence": ev,
            "counts": {k: len(v) for k, v in scene.items()}, "osm_time": osm.get("osm3s", {}).get("timestamp_osm_base", ""),
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or "diorama.html"
    open(dest, "w", encoding="utf-8").write(page)
    print(f"wrote {dest} ({'cached' if cached else 'fresh'} OpenStreetMap data, {data['osm_time'] or 'time unknown'})")
    print("  " + ", ".join(f"{v} {k}" for k, v in data["counts"].items()))
    if not scene["buildings"]:
        print("  note: no buildings mapped here in OpenStreetMap; the model will be flat")
    if "distance_m" in ev:
        print(f"  camera to target: {ev['distance_m']} m, facing {ev['camera']['bearing']} degrees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
