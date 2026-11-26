#!/usr/bin/env python3
"""A before/after satellite comparison: a slider page readers can drag, with the dates, the imagery source and your
annotations on the image. Standard library only.

Two ways in:
  1. Your own two images (licensed commercial imagery, screenshots you are allowed to publish):
       before_after.py --before-image a.jpg --after-image b.jpg --before-label "3 Aug 2023" --after-label "9 Aug 2023" \\
           --credit "Satellite images: Planet Labs PBC" --title "..."
  2. Free NASA imagery for a place and two dates (HLS 30 m, or VIIRS / MODIS for big areas). The script looks at the
     days around each date and picks the clearest pass (least cloud, least missing data):
       before_after.py --lat 20.873 --lon -156.677 --km 2.5 --before 2023-08-03 --after 2023-08-12 --title "..."

Imagery from NASA GIBS (https://www.earthdata.nasa.gov/gibs): keyless and open; the page credits it. The date search
fetches small previews (one per day in the window, cached in ~/.cache/osint-visuals); keep the window short.
"""
import argparse
import base64
import hashlib
import html
import json
import math
import os
import struct
import sys
import time
import urllib.parse
import urllib.request
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "before-after.html")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "osint-visuals", "gibs")
UA = "osint-visuals/0.2 (open-source evidence graphics; https://github.com/Ghongha007/osint-visuals)"
WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
LAYERS = {   # name: (GIBS layer, metres per pixel, what to write on the graphic)
    "hls": ("HLS_S30_Nadir_BRDF_Adjusted_Reflectance", 30, "NASA HLS (Sentinel-2), 30 m"),
    "hls-landsat": ("HLS_L30_Nadir_BRDF_Adjusted_Reflectance", 30, "NASA HLS (Landsat), 30 m"),
    "viirs": ("VIIRS_SNPP_CorrectedReflectance_TrueColor", 250, "NASA VIIRS (Suomi NPP), about 250 m"),
    "modis": ("MODIS_Terra_CorrectedReflectance_TrueColor", 250, "NASA MODIS (Terra), about 250 m"),
}


def get(url, binary=True):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:20])
    if os.path.exists(key):
        return Path(key).read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            Path(key).write_bytes(data); time.sleep(0.15)          # gentle on a shared public service
            return data
        except Exception as ex:
            if attempt == 2: sys.exit(f"NASA GIBS request failed ({ex}); try again later")
            time.sleep(3 * (attempt + 1))


def wms(layer, day, bbox, w, h, fmt="image/png"):
    q = {"SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer, "STYLES": "", "CRS": "EPSG:4326",
         "BBOX": ",".join(f"{v:.6f}" for v in bbox), "WIDTH": w, "HEIGHT": h, "FORMAT": fmt, "TIME": day.isoformat()}
    if fmt == "image/png": q["TRANSPARENT"] = "TRUE"
    return get(WMS + "?" + urllib.parse.urlencode(q))


def png_pixels(data):
    """Minimal PNG decoder (8-bit RGB/RGBA/grey, non-interlaced): returns (w, h, channels, rows of bytes)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n": return None
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]; kind = data[pos + 4:pos + 8]; body = data[pos + 8:pos + 8 + n]; pos += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace: return None
            ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
            if ch is None: return None
        elif kind == b"IDAT": idat += body
        elif kind == b"IEND": break
    raw, stride, rows, prev = zlib.decompress(idat), w * ch, [], bytearray(w * ch)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0; b = prev[i]; c = prev[i - ch] if i >= ch else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return w, h, ch, rows


def clear_score(data):
    """Share of the preview that has data and is not cloud: 0 (empty or all cloud) to 1 (all clear)."""
    px = png_pixels(data)
    if not px: return 0.0
    w, h, ch, rows = px; good = total = 0
    for row in rows:
        for i in range(0, len(row), ch):
            total += 1
            r, g, b = (row[i], row[i], row[i]) if ch < 3 else (row[i], row[i + 1], row[i + 2])
            if ch in (2, 4) and row[i + ch - 1] < 128: continue                 # no data (transparent)
            if r + g + b < 15: continue                                        # no data (black fill)
            if min(r, g, b) > 175 and max(r, g, b) - min(r, g, b) < 35: continue   # bright and grey: cloud
            good += 1
    return good / total if total else 0.0


def best_pass(layer, target, window, bbox, direction):
    """Scan the window (before: back from the date; after: forward) and return (day, score, tried)."""
    days = [target - timedelta(days=i) if direction < 0 else target + timedelta(days=i) for i in range(window + 1)]
    best, tried = None, []
    for d in days:
        s = clear_score(wms(layer, d, bbox, 96, 96)); tried.append((d.isoformat(), round(s, 2)))
        if best is None or s > best[1] + 0.02: best = (d, s)
        if s > 0.97: break                                          # good enough: stop early
    return best[0], best[1], tried


def data_uri(path_or_bytes, mime=None):
    if isinstance(path_or_bytes, bytes):
        return f"data:{mime or 'image/jpeg'};base64," + base64.b64encode(path_or_bytes).decode()
    ext = os.path.splitext(path_or_bytes)[1].lower()
    mime = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(Path(path_or_bytes).read_bytes()).decode()


def fmt_day(d):
    return f"{d.day} {d.strftime('%b %Y')}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before-image"); ap.add_argument("--after-image")
    ap.add_argument("--before-label", default="Before"); ap.add_argument("--after-label", default="After")
    ap.add_argument("--credit", default="", help="who the images belong to (required with your own images)")
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--km", type=float, default=3, help="km from the centre to the edge of the picture (NASA mode)")
    ap.add_argument("--before", help="YYYY-MM-DD"); ap.add_argument("--after", help="YYYY-MM-DD")
    ap.add_argument("--layer", choices=list(LAYERS), default="hls")
    ap.add_argument("--window", type=int, default=12, help="days to search for a clearer pass (0 = the exact dates)")
    ap.add_argument("--mark", action="append", default=[], help='annotation "LAT,LON,text" or "X%%,Y%%,text" (repeatable)')
    ap.add_argument("--title", default="Before and after"); ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="anything else the reader should know about where this came from")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    marks, info, bbox = [], {}, None
    if a.before_image and a.after_image:
        if not a.credit:
            print("note: no --credit given; say who owns these images before you publish")
        imgs = [data_uri(a.before_image), data_uri(a.after_image)]
        labels = [a.before_label, a.after_label]; credit = a.credit or "Images: source not stated"
    elif a.lat is not None and a.lon is not None and a.before and a.after:
        layer, mpp, lname = LAYERS[a.layer]
        dlat = a.km / 110.6; dlon = a.km / (111.32 * math.cos(math.radians(a.lat)))
        bbox = (a.lat - dlat, a.lon - dlon, a.lat + dlat, a.lon + dlon)        # WMS 1.3.0 EPSG:4326 order: lat, lon
        b0, a0 = date.fromisoformat(a.before), date.fromisoformat(a.after)
        picks = []
        for target, direction in ((b0, -1), (a0, 1)):
            if a.window > 0:
                d, s, tried = best_pass(layer, target, a.window, bbox, direction)
                print(f"  {'before' if direction < 0 else 'after '} {target}: picked {d} (clear {s:.0%}); looked at " +
                      ", ".join(f"{t[0][5:]} {t[1]:.0%}" for t in tried))
            else:
                d, s = target, clear_score(wms(layer, target, bbox, 96, 96))
            if s < 0.05: sys.exit(f"no usable {a.layer} imagery near {target} for this place; try --layer viirs, a wider --window or other dates")
            picks.append((d, s))
        px = max(256, min(2048, round(2 * a.km * 1000 / mpp * 1.15)))      # about the native resolution: the page smooths it when scaling up
        imgs = [data_uri(wms(layer, d, bbox, px, px, "image/jpeg")) for d, _ in picks]
        labels = [fmt_day(d) for d, _ in picks]
        credit = (f"Imagery: {lname}, via NASA GIBS (ESDIS)" + ("; contains modified Copernicus Sentinel data " +
                  ", ".join(sorted({str(d.year) for d, _ in picks})) if a.layer == "hls" else "") + ".")
        info = {"layer": a.layer, "picked": [d.isoformat() for d, _ in picks], "clear": [round(s, 2) for _, s in picks],
                "km": a.km, "lat": a.lat, "lon": a.lon}
    else:
        sys.exit("give --before-image and --after-image, or --lat, --lon, --before and --after")
    for m in a.mark:
        x, y, text = m.split(",", 2)
        if x.strip().endswith("%"):
            marks.append({"x": float(x.strip()[:-1]) / 100, "y": float(y.strip()[:-1]) / 100, "t": text.strip()})
        elif bbox:
            la, lo = float(x), float(y)
            marks.append({"x": (lo - bbox[1]) / (bbox[3] - bbox[1]), "y": (bbox[2] - la) / (bbox[2] - bbox[0]), "t": text.strip()})
        else:
            sys.exit("--mark with coordinates needs the NASA mode; with your own images give X%,Y% instead")
    data = {"title": a.title, "subtitle": a.subtitle, "imgs": imgs, "labels": labels, "credit": credit, "source": a.source,
            "marks": marks, "info": info, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    page = Path(TEMPLATE).read_text(encoding="utf-8")
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or "before-after.html"
    Path(dest).write_text(page, encoding="utf-8")
    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB): {labels[0]} vs {labels[1]}")
    if info and min(info["clear"]) < 0.6:
        print("  note: one picture is still partly cloudy or has gaps; say so in the caption, or try other dates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
