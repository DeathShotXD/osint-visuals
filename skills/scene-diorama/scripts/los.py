#!/usr/bin/env python3
"""Prototype: can the camera actually see the target? A terrain and building line-of-sight check for scene-diorama.

This is a probe, not the finished skill. It reuses the diorama's Overpass download and local metre projection, adds
terrain from Mapzen Terrarium tiles (keyless, elevation encoded in RGB), and answers one question the model never
asks: is the sight line blocked, and where?

    los.py --lat 46.0514 --lon 14.5061 --radius 160 \
           --camera 46.05098,14.50712 --camera-height 9 \
           --target 46.05143,14.50606 --target-height 0 \
           --title "Can this camera see the square?" --out los.html

Writes an SVG profile and prints the verdict. Standard library only. Terrain tiles are cached in
~/.cache/osint-visuals. Check the source's terms before publishing; terrain is a model, not a survey.
"""
import argparse
import importlib.util
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import diorama  # noqa: E402  (same folder, deliberately imported as a module)

CACHE = os.path.join(os.path.expanduser("~"), ".cache", "osint-visuals")
UA = "osint-visuals-los/0.1 (prototype; https://github.com/Ghongha007/osint-visuals)"
TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def png_pixels(data):
    """Minimal PNG decoder, same rules as before-after: 8-bit, non-interlaced, grey/RGB/GA/RGBA."""
    import struct
    import zlib
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, w, h, ch = 8, b"", 0, 0, 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace:
                return None
            ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
            if ch is None:
                return None
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    raw, stride, rows, prev = zlib.decompress(idat), w * ch, [], bytearray(w * ch)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, ch, rows


def elevation_from_rgb(r, g, b):
    """Terrarium encoding: (R * 256 + G + B / 256) - 32768 metres."""
    return r * 256 + g + b / 256 - 32768


class Terrain:
    """Terrarium tile reader with a disk cache. Nearest pixel is enough at z15 (about 5 m a pixel)."""

    def __init__(self, z=15):
        self.z = z
        self.tiles = {}

    def tile(self, x, y):
        key = (self.z, x, y)
        if key in self.tiles:
            return self.tiles[key]
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, f"terrarium-{self.z}-{x}-{y}.png")
        if os.path.exists(path):
            data = open(path, "rb").read()
        else:
            req = urllib.request.Request(TILES.format(z=self.z, x=x, y=y), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(path, "wb").write(data)
        px = png_pixels(data)
        if not px:
            raise ValueError(f"terrain tile {self.z}/{x}/{y} is not a plain 8-bit PNG")
        self.tiles[key] = px
        return px

    def elevation(self, lat, lon):
        n = 2 ** self.z
        fx = (lon + 180) / 360 * n
        fy = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        x, y = int(fx), int(fy)
        w, h, ch, rows = self.tile(x, y)
        px = min(w - 1, max(0, int((fx - x) * w)))
        py = min(h - 1, max(0, int((fy - y) * h)))
        row = rows[py]
        r, g, b = row[px * ch], row[px * ch + 1], row[px * ch + 2]
        return elevation_from_rgb(r, g, b)


def inside(x, z, poly):
    """Ray casting in the projected metre frame."""
    hit = False
    for i in range(len(poly)):
        x1, z1 = poly[i - 1]
        x2, z2 = poly[i]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / ((z2 - z1) or 1e-12) + x1:
            hit = not hit
    return hit


def obstruction(x, z, ground, buildings):
    """Highest thing at this point: the ground, or a building footprint on top of it."""
    top, who = ground, None
    for b in buildings:
        if b["h"] > 0 and inside(x, z, b["p"]):
            h = ground + b["h"]
            if h > top:
                top, who = h, b
    return top, who


def profile(cam, target, eye, target_z, ground, buildings, step=2.0):
    """Sample the segment. cam/target are (x, z) metres, eye/target_z are absolute elevations."""
    dx, dz = target[0] - cam[0], target[1] - cam[1]
    dist = math.hypot(dx, dz)
    n = max(1, int(dist / step))
    rows = []
    for i in range(n + 1):
        t = i / n
        x, z = cam[0] + dx * t, cam[1] + dz * t
        g = ground(x, z)
        top, who = obstruction(x, z, g, buildings)
        line = eye + (target_z - eye) * t
        rows.append({"t": round(t, 4), "d": round(dist * t, 1), "x": round(x, 2), "z": round(z, 2),
                     "ground": round(g, 1), "line": round(line, 2), "top": round(top, 1),
                     "margin": round(line - top, 2), "blocked": line < top,
                     "kind": "building" if who else "terrain",
                     "building": (who or {}).get("n") or (who or {}).get("k") or ("building" if who else "")})
    return dist, rows


def summarise(rows, clearance=0.3):
    """First real obstruction. Bare ground under a line that is coming down to a target does not count."""
    def blocked(r):
        return r["line"] < r["top"] or (r["top"] > r["ground"] + 0.05 and r["margin"] < clearance)

    hits = [r for r in rows[1:-1] if blocked(r)]
    if not hits:
        return {"clear": True, "first": None, "worst": min((r["margin"] for r in rows), default=0.0)}
    first = hits[0]
    worst = min(hits, key=lambda r: r["margin"])
    return {"clear": False, "first": first, "worst": worst}


def los_for(cam, target, cam_h, target_h, ground, buildings, step=2.0, clearance=0.3):
    """Everything diorama.py needs: eye and target elevations, the profile, and the verdict."""
    eye = ground(*cam) + cam_h
    target_z = ground(*target) + target_h
    dist, rows = profile(cam, target, eye, target_z, ground, buildings, max(1.0, step))
    verdict = summarise(rows, clearance)
    return {"clear": verdict["clear"], "block": verdict["first"], "worst": verdict.get("worst"), "rows": rows,
            "distance_m": round(dist, 1), "eye_m": round(eye, 1), "target_m": round(target_z, 1), "clearance": clearance}


def svg_page(rows, dist, verdict, meta):
    """A small profile chart: ground, obstruction envelope, sight line and the blocked stretch."""
    W, H = 1200, 460
    ml, mr, mt, mb = 70, 40, 78, 66
    lows = [r["ground"] for r in rows] + [r["line"] for r in rows]
    highs = [max(r["ground"], r["top"]) for r in rows] + [r["line"] for r in rows]
    lo, hi = min(lows) - 8, max(highs) + 8
    if hi - lo < 20:
        hi = lo + 20

    def X(d):
        return ml + d / max(dist, 1e-9) * (W - ml - mr)

    def Y(v):
        return mt + (hi - v) / (hi - lo) * (H - mt - mb)

    ground_pts = " ".join(f"{X(r['d']):.1f},{Y(r['ground']):.1f}" for r in rows)
    top_pts = " ".join(f"{X(r['d']):.1f},{Y(max(r['ground'], r['top'])):.1f}" for r in rows)
    line_pts = " ".join(f"{X(r['d']):.1f},{Y(r['line']):.1f}" for r in rows)
    base = Y(lo)
    fill_ground = f"{X(0):.1f},{base:.1f} " + ground_pts + f" {X(dist):.1f},{base:.1f}"
    fill_top = f"{X(0):.1f},{base:.1f} " + top_pts + f" {X(dist):.1f},{base:.1f}"
    block = [r for r in rows if r["blocked"]]
    band = ""
    if block:
        x0, x1 = X(block[0]["d"]), X(block[-1]["d"])
        band = f'<rect x="{x0:.1f}" y="{mt}" width="{max(1.5, x1 - x0):.1f}" height="{H - mt - mb}" fill="#e2574c" opacity=".10"/>'
    colour = "#2f9e6b" if verdict["clear"] else "#d9463b"
    verdict_text = "LINE OF SIGHT CLEAR" if verdict["clear"] else "LINE OF SIGHT BLOCKED"
    detail = ("No terrain or building breaks the line by more than the clearance."
              if verdict["clear"] else
              f"First obstruction at {verdict['first']['d']} m: {verdict['first']['top']} m, "
              f"line {verdict['first']['line']} m, {abs(verdict['first']['margin'])} m into the obstacle"
              + (f" ({verdict['first']['building']})" if verdict["first"]["building"] else " (terrain)"))
    ticks = "".join(
        f'<line x1="{X(d):.1f}" y1="{H - mb}" x2="{X(d):.1f}" y2="{H - mb + 5}" stroke="#c9bfa8"/>'
        f'<text x="{X(d):.1f}" y="{H - mb + 20}" fill="#8a7a66" font-size="11" text-anchor="middle">{int(d)} m</text>'
        for d in range(0, int(dist) + 1, max(20, int(dist / 6 // 10 * 10 or 20))))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">
<title>{meta['title']}</title>
<rect width="{W}" height="{H}" fill="#f6f1e6"/>
<text x="{ml}" y="34" fill="#2b2b28" font-size="22" font-weight="700">{meta['title']}</text>
<text x="{ml}" y="56" fill="#8a7a66" font-size="12">{meta['place']} - camera {meta['cam'][0]:.5f},{meta['cam'][1]:.5f} at {meta['cam_h']} m,
target {meta['target'][0]:.5f},{meta['target'][1]:.5f} - {dist:.0f} m apart</text>
<rect x="{ml}" y="{mt}" width="{W - ml - mr}" height="{H - mt - mb}" fill="#fffdf7" stroke="#ded4bd"/>
{band}
<polygon points="{fill_ground}" fill="#e8dfc9"/>
<polygon points="{fill_top}" fill="#c9b48c" opacity=".55"/>
<polyline points="{ground_pts}" fill="none" stroke="#8a7a66" stroke-width="1.4"/>
<polyline points="{top_pts}" fill="none" stroke="#a98d5f" stroke-width="1"/>
<polyline points="{line_pts}" fill="none" stroke="{colour}" stroke-width="2.6"/>
{ticks}
<circle cx="{X(0):.1f}" cy="{Y(rows[0]['line']):.1f}" r="4.5" fill="#1f2b2e"/>
<circle cx="{X(dist):.1f}" cy="{Y(rows[-1]['line']):.1f}" r="4.5" fill="{colour}"/>
<text x="{X(0) + 8:.1f}" y="{Y(rows[0]['line']) - 10:.1f}" fill="#1f2b2e" font-size="11">camera, eye {rows[0]['line']:.1f} m</text>
<text x="{X(dist) - 8:.1f}" y="{Y(rows[-1]['line']) - 10:.1f}" fill="#1f2b2e" font-size="11" text-anchor="end">target {rows[-1]['line']:.1f} m</text>
<text x="{W - mr}" y="34" fill="{colour}" font-size="13" font-weight="700" text-anchor="end">{verdict_text}</text>
<text x="{W - mr}" y="54" fill="#6b5c48" font-size="11" text-anchor="end">{detail}</text>
<text x="{ml}" y="{H - 8}" fill="#8a7a66" font-size="10">Terrain: Mapzen Terrarium (SRTM and others). Buildings: OpenStreetMap, heights from tags or estimated. Model, not a survey.</text>
</svg>
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=160, help="half the side of the OSM square, metres")
    ap.add_argument("--camera", required=True, help="LAT,LON where the camera stood")
    ap.add_argument("--camera-height", type=float, default=1.7)
    ap.add_argument("--target", required=True, help="LAT,LON of the thing being filmed")
    ap.add_argument("--target-height", type=float, default=0.0, help="height of the target above its ground")
    ap.add_argument("--step", type=float, default=2.0, help="sampling step along the line, metres")
    ap.add_argument("--clearance", type=float, default=0.3, help="metres the line must clear an obstacle by")
    ap.add_argument("--z", type=int, default=15, help="terrain tile zoom (13 to 15)")
    ap.add_argument("--title", default="Can the camera see the target?")
    ap.add_argument("--place", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    r = max(60, min(250, a.radius))
    P = diorama.project(a.lat, a.lon)
    kx = 111320 * math.cos(math.radians(a.lat))
    dlat = r * 1.25 / 110540
    dlon = r * 1.25 / kx
    osm, cached = diorama.overpass(round(a.lat - dlat, 6), round(a.lon - dlon, 6),
                                   round(a.lat + dlat, 6), round(a.lon + dlon, 6))
    scene = diorama.build(osm, P, r)
    cam, target = diorama.point(a.camera, P), diorama.point(a.target, P)
    cam_ll, target_ll = tuple(map(float, a.camera.split(","))), tuple(map(float, a.target.split(",")))

    def to_ll(x, z):
        return (a.lat - z / 110540, a.lon + x / kx)

    terrain = Terrain(z=max(13, min(15, a.z)))

    def ground(x, z):
        lat, lon = to_ll(x, z)
        return terrain.elevation(lat, lon)

    # the building the camera stands in is not an obstruction: the camera is on its facade, looking out
    buildings = [b for b in scene["buildings"] if not inside(cam[0], cam[1], b["p"])]
    los = los_for(cam, target, a.camera_height, a.target_height, ground, buildings, a.step, a.clearance)
    data = {"title": a.title, "place": a.place, "source": a.source, "camera": cam_ll, "camera_height": a.camera_height,
            "target": target_ll, "target_height": a.target_height,
            "distance_m": los["distance_m"], "eye_m": los["eye_m"], "target_m": los["target_m"],
            "clearance": a.clearance, "clear": los["clear"], "block": los["block"], "rows": los["rows"],
            "counts": {k: len(v) for k, v in scene.items()},
            "terrain_tiles_cached": len(terrain.tiles),
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    dest = a.out or "los.svg"
    svg = svg_page(los["rows"], los["distance_m"], {"clear": los["clear"], "first": los["block"]},
                   {"title": a.title, "place": a.place, "cam": cam_ll, "cam_h": a.camera_height, "target": target_ll})
    open(dest, "w", encoding="utf-8").write(svg)
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  camera eye {los['eye_m']} m, target {los['target_m']} m, {los['distance_m']:.0f} m apart, "
          f"{len(los['rows'])} samples, step {a.step} m")
    if los["clear"]:
        print("  clear: nothing on the profile rises within the clearance of the line")
    else:
        b = los["block"]
        print(f"  blocked at {b['d']} m: {b['kind']} {b['top']} m vs line {b['line']} m "
              f"({abs(b['margin'])} m into it){', ' + b['building'] if b['building'] else ''}")
        w = los.get("worst")
        if w and w is not b:
            print(f"  worst point {w['d']} m: {w['kind']} {w['top']} m vs line {w['line']} m")
    print("  note: terrain tiles are a model; buildings and heights come from OSM tags or estimates. Verify before publishing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())