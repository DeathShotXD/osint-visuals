#!/usr/bin/env python3
"""Turn ship (AIS) or aircraft (ADS-B) positions into an animated, evidence-first track map. Standard library only.

Reads one CSV (one row per position report), works out what an investigator looks for, and writes ONE html file:
  - signal gaps   : no report for longer than --gap (a ship "going dark", a transponder switched off)
  - impossible jumps: consecutive reports that imply a speed above --max-speed (spoofed or bad positions)
  - meetings      : two tracks within --meet-km of each other at the same time (e.g. ship-to-ship transfers)

  track.py positions.csv --title "Tanker X goes dark" --source "AIS via MarineTraffic, downloaded 2026-06-20"
  track.py flights.csv --kind aircraft --gap 5m --out flight.html

The CSV needs a time column and latitude/longitude columns (names are detected: time/timestamp/datetime/basedatetime,
lat/latitude, lon/lng/long/longitude). An id column (id/mmsi/imo/icao/icao24/callsign/name/vessel) splits it into
several tracks. Times may be ISO 8601 (with or without a zone; no zone means UTC) or Unix seconds.
"""
import argparse
import csv
import html
import json
import math
import os
import re
import sys
from datetime import datetime, timezone, timedelta


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "track.html")
COLOURS = ["#4FC3F7", "#FFB74D", "#81C784", "#F06292", "#BA68C8", "#4DB6AC", "#FFF176"]
NAMES = {
    "time": ["time", "timestamp", "datetime", "date_time", "basedatetime", "ts", "utc", "time_utc", "position_time"],
    "lat": ["lat", "latitude", "y"],
    "lon": ["lon", "lng", "long", "longitude", "x"],
    "id": ["id", "mmsi", "imo", "icao", "icao24", "hex", "callsign", "flight", "name", "vessel", "vessel_name", "ship"],
}


def pick(header, kind):
    low = {h.strip().lower(): h for h in header}
    for n in NAMES[kind]:
        if n in low:
            return low[n]
    return None


def parse_time(s):
    s = s.strip()
    if not s:
        raise ValueError("empty time")
    try:
        v = float(s)
        if v > 1e11:                      # milliseconds
            v /= 1000
        return datetime.fromtimestamp(v, tz=timezone.utc)
    except ValueError:
        pass
    t = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" UTC", ""))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse_span(s):
    """'2h', '30m', '90s', '1.5h' -> seconds."""
    s = s.strip().lower()
    unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(s[-1])
    return float(s[:-1]) * unit if unit else float(s)


def fmt_offset(mins):
    sign = "-" if mins < 0 else "+"
    return f"{sign}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}"


def tz_segments(spec, t0, t1):
    """The clock's time zone over [t0, t1] as [[start unix time, offset in minutes, label], ...].

    An offset like +04:00 gives one segment. A zone name like Asia/Dubai or Europe/London is looked up, and a new
    segment starts at each daylight-saving change inside the period, so the clock is right on both sides of it."""
    s = spec.strip()
    if s.upper() in ("Z", "UTC", "GMT"):
        s = "+00:00"
    if s[:1] in "+-":
        m = re.fullmatch(r"([+-])(\d{1,2})(?::?(\d{2}))?", s)
        mins = m and (-1 if m.group(1) == "-" else 1) * (int(m.group(2)) * 60 + int(m.group(3) or 0))
        if not m or abs(mins) > 14 * 60 or int(m.group(3) or 0) >= 60:
            sys.exit(f"--tz {spec!r}: not a valid offset. Use one like +04:00 or -05:30, or a zone name like Asia/Dubai.")
        return [[int(t0.timestamp()), mins, "UTC" if mins == 0 else "UTC" + fmt_offset(mins)]]
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(s)
    except Exception:                       # unknown name, or no time zone database (Windows: pip install tzdata)
        sys.exit(f"--tz {spec!r}: unknown time zone. Use an offset like +04:00, or a zone name like Asia/Dubai "
                 "(on Windows, run 'pip install tzdata' first).")
    off = lambda t: int(t.astimezone(zone).utcoffset().total_seconds() // 60)
    label = lambda mins: f"{s} (UTC{fmt_offset(mins)})"
    cur = off(t0); segs = [[int(t0.timestamp()), cur, label(cur)]]
    t, step = t0, timedelta(hours=1)
    while t < t1:
        n = min(t + step, t1); o = off(n)
        if o != cur:                         # a change happened in (t, n]: narrow it down to the second
            lo, hi = t, n
            while (hi - lo).total_seconds() > 1:
                mid = lo + (hi - lo) / 2
                if off(mid) == cur: lo = mid
                else: hi = mid
            segs.append([math.ceil(hi.timestamp()), o, label(o)]); cur = o
        t = n
    return segs


def km(a, b):
    """Great-circle distance in km between (lat, lon) pairs."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1, math.sqrt(h)))


def read_tracks(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path}: no rows")
    header = list(rows[0].keys())
    ct, cla, clo, cid = pick(header, "time"), pick(header, "lat"), pick(header, "lon"), pick(header, "id")
    if not (ct and cla and clo):
        sys.exit(f"{path}: need time, latitude and longitude columns; found {header}")
    tracks, skipped = {}, 0
    for r in rows:
        try:
            t = parse_time(r[ct]); la = float(r[cla]); lo = float(r[clo])
        except (ValueError, TypeError):
            skipped += 1; continue
        if not (-90 <= la <= 90 and -180 <= lo <= 180) or (la == 0 and lo == 0):
            skipped += 1; continue          # 0,0 is the classic "no fix" value
        key = (r.get(cid) or "").strip() if cid else ""
        tracks.setdefault(key or "Track", []).append((t, la, lo))
    if not tracks:
        sys.exit(f"{path}: none of the {len(rows)} rows could be used. Every row had a time, latitude or longitude that "
                 "couldn't be read, a position outside the map, or 0,0 (no fix).")
    for k in tracks:
        tracks[k] = sorted(set(tracks[k]))
    return tracks, skipped, cid


def knots(a, b):
    dt = (b[0] - a[0]).total_seconds()
    return float("inf") if dt <= 0 else km(a[1:], b[1:]) / (dt / 3600) / 1.852


def analyse(tracks, gap_s, max_kn, meet_km, meet_s, near_km=10.0):
    gaps, jumps, out = [], [], []
    for i, (name, pts) in enumerate(tracks.items()):
        dist, k, bad = 0.0, 1, set()
        while k < len(pts):
            a, b = pts[k - 1], pts[k]
            d = km(a[1:], b[1:]); dt = (b[0] - a[0]).total_seconds()
            if dt > gap_s:
                gaps.append({"track": name, "from": a[0].isoformat(), "to": b[0].isoformat(), "hours": round(dt / 3600, 1),
                             "km": round(d, 1), "a": [a[1], a[2]], "b": [b[1], b[2]],
                             "near": nearby(tracks, name, a, b, gap_s, near_km)})
            elif knots(a, b) > max_kn:
                c = pts[k + 1] if k + 1 < len(pts) else None
                if c and knots(b, c) > max_kn and knots(a, c) <= max_kn:      # one fix out of line, then back: a bad position
                    jumps.append({"track": name, "at": b[0].isoformat(), "knots": round(knots(a, b)), "outlier": True,
                                  "a": [a[1], a[2]], "b": [b[1], b[2]]})
                    bad.add(k); dist += km(a[1:], c[1:]); k += 2; continue
                jumps.append({"track": name, "at": b[0].isoformat(), "knots": round(knots(a, b)), "outlier": False,
                              "a": [a[1], a[2]], "b": [b[1], b[2]]})
            dist += d; k += 1
        out.append({"id": name, "colour": COLOURS[i % len(COLOURS)], "km": round(dist, 1), "points": len(pts),
                    "start": pts[0][0].isoformat(), "end": pts[-1][0].isoformat(),
                    "pts": [[int(p[0].timestamp()), round(p[1], 5), round(p[2], 5)] for n, p in enumerate(pts) if n not in bad]})   # bad fixes are flagged, not drawn
    meets = find_meetings(tracks, gap_s, meet_km, meet_s)
    return out, gaps, jumps, meets


def position_at(pts, t, gap_s):
    """Linear position at time t, or None outside the track or inside a signal gap."""
    lo, hi = 0, len(pts) - 1
    if not pts or t < pts[0][0] or t > pts[-1][0]:
        return None
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= t: lo = mid
        else: hi = mid
    a, b = pts[lo], pts[hi]
    span = (b[0] - a[0]).total_seconds()
    if span > gap_s:
        return None
    k = 0 if span == 0 else (t - a[0]).total_seconds() / span
    return (a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)


def nearby(tracks, name, a, b, gap_s, near_km):
    """Other vessels close to where a track went dark (its last report) or reappeared (its next report)."""
    found = []
    for other, pts in tracks.items():
        if other == name:
            continue
        for label, fix in (("went dark", a), ("reappeared", b)):
            p = position_at(pts, fix[0], gap_s)
            if p and km(p, fix[1:]) <= near_km:
                found.append({"track": other, "when": label, "km": round(km(p, fix[1:]), 1)})
    return found


def find_meetings(tracks, gap_s, meet_km, meet_s):
    names, found = list(tracks), []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            A, B = tracks[names[i]], tracks[names[j]]
            t0, t1 = max(A[0][0], B[0][0]), min(A[-1][0], B[-1][0])
            if t0 >= t1:
                continue
            run, t, step = None, t0, timedelta(minutes=5)
            while t <= t1 + step:
                pa, pb = position_at(A, t, gap_s), position_at(B, t, gap_s)
                close = pa and pb and km(pa, pb) <= meet_km
                if close and run is None:
                    run = [t, t, km(pa, pb), pa, pb]
                elif close:
                    run[1] = t; run[2] = min(run[2], km(pa, pb))
                elif run is not None:
                    if (run[1] - run[0]).total_seconds() >= meet_s:
                        found.append({"tracks": [names[i], names[j]], "from": run[0].isoformat(), "to": run[1].isoformat(),
                                      "hours": round((run[1] - run[0]).total_seconds() / 3600, 1), "min_km": round(run[2], 2),
                                      "at": [(run[3][0] + run[4][0]) / 2, (run[3][1] + run[4][1]) / 2]})
                    run = None
                t += step
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv")
    ap.add_argument("--title", default="Track")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", default="", help="where the positions came from, shown on the graphic (strongly recommended)")
    ap.add_argument("--kind", choices=["ship", "aircraft"], default="ship")
    ap.add_argument("--gap", default=None, help="silence that counts as a signal gap, e.g. 2h, 30m (default: 2h ships, 5m aircraft)")
    ap.add_argument("--max-speed", type=float, default=None, help="knots; faster jumps are flagged (default: 50 ships, 700 aircraft)")
    ap.add_argument("--meet-km", type=float, default=1.0, help="distance that counts as a meeting (km)")
    ap.add_argument("--meet-min", type=float, default=30, help="minimum length of a meeting (minutes)")
    ap.add_argument("--tz", default="+00:00", help="time zone for the on-screen clock: an offset like +04:00, or a zone name like Asia/Dubai, "
                    "which follows daylight saving (default UTC)")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    gap_s = parse_span(a.gap or ("2h" if a.kind == "ship" else "5m"))
    max_kn = a.max_speed or (50 if a.kind == "ship" else 700)
    tracks, skipped, cid = read_tracks(a.csv)
    t_first = min(p[0] for pts in tracks.values() for p in pts); t_last = max(p[0] for pts in tracks.values() for p in pts)
    zones = tz_segments(a.tz, t_first, t_last)
    out, gaps, jumps, meets = analyse(tracks, gap_s, max_kn, a.meet_km, a.meet_min * 60)
    lats = [p[1] for t in out for p in t["pts"]] + [j["b"][0] for j in jumps]   # flagged positions stay in frame
    lons = [p[2] for t in out for p in t["pts"]] + [j["b"][1] for j in jumps]
    data = {"title": a.title, "subtitle": a.subtitle, "source": a.source, "kind": a.kind, "tz": a.tz, "tz_segments": zones, "theme": a.theme,
            "gap_hours": round(gap_s / 3600, 2), "max_knots": max_kn, "meet_km": a.meet_km,
            "bounds": [[min(lons), min(lats)], [max(lons), max(lats)]], "tracks": out, "gaps": gaps, "jumps": jumps,
            "meetings": meets, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "input": os.path.basename(a.csv), "skipped_rows": skipped}
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or os.path.splitext(a.csv)[0] + "_track.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dest}")
    print(f"{len(out)} track(s), {sum(t['points'] for t in out)} positions, {skipped} rows skipped")
    print(f"clock: {zones[0][2]}" + "".join(f", then {z[2]} from {datetime.fromtimestamp(z[0], timezone.utc):%Y-%m-%d %H:%M} UTC" for z in zones[1:]))
    for g in gaps:
        print(f"  signal gap  {g['track']}: {g['hours']} h from {g['from']} ({g['km']} km between last and next report)")
    for g in gaps:
        for n in g["near"]:
            print(f"    {n['track']} was {n['km']} km away when {g['track']} {n['when']}")
    for j in jumps:
        what = "one position out of line" if j["outlier"] else "jump"
        print(f"  {what:11s} {j['track']}: {j['knots']} kn implied at {j['at']} (check for spoofing or a bad fix)")
    for m in meets:
        print(f"  meeting     {' + '.join(m['tracks'])}: within {m['min_km']} km for {m['hours']} h from {m['from']}")
    if not a.source:
        print("note: no --source given; the graphic will say 'Source not stated'. Name where the positions came from.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
