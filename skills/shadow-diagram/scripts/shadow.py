#!/usr/bin/env python3
"""Draw a chronolocation diagram: when could this shadow have been cast? Standard library only.

Given a place, a date and a measured shadow (its compass direction, and/or the ratio of an object's height to its
shadow length), works out the windows of local time that fit, and writes ONE html page with a sun-path compass,
the day's sun elevation, the matching windows and, if given, a check of a claimed time.

  shadow.py --lat -1.2864 --lon 36.8172 --date 2026-08-10 --tz +03:00 --shadow-azimuth 250 --tolerance 6 \\
            --claimed 16:30 --place "Nairobi, Kenya" --title "Was this photo taken in the afternoon?"
  shadow.py --lat 28.6139 --lon 77.2090 --date 2026-11-16 --tz Asia/Kolkata --height 1.8 --shadow-length 2.4

Sun position: NOAA solar position equations, no atmospheric refraction correction (the same maths as
osint-skills/chronolocate/sun.py). Results near the horizon (sun under ~3 degrees) are less reliable.
"""
import argparse
import html
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

R, D = math.radians, math.degrees

def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "shadow.html")


def sun_position(lat, lon, when):
    """(azimuth, elevation) in degrees; azimuth clockwise from true north. `when` must be timezone-aware."""
    u = when.astimezone(timezone.utc)
    jd = u.toordinal() + 1721424.5 + (u.hour + u.minute / 60 + u.second / 3600) / 24
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (math.sin(R(m)) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(R(2 * m)) * (0.019993 - 0.000101 * t) + math.sin(R(3 * m)) * 0.000289)
    omega = 125.04 - 1934.136 * t
    lam = l0 + c - 0.00569 - 0.00478 * math.sin(R(omega))
    eps = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60 + 0.00256 * math.cos(R(omega))
    decl = math.asin(math.sin(R(eps)) * math.sin(R(lam)))
    y = math.tan(R(eps / 2)) ** 2
    eot = 4 * D(y * math.sin(2 * R(l0)) - 2 * e * math.sin(R(m)) + 4 * e * y * math.sin(R(m)) * math.cos(2 * R(l0))
                - 0.5 * y * y * math.sin(4 * R(l0)) - 1.25 * e * e * math.sin(2 * R(m)))
    minutes = u.hour * 60 + u.minute + u.second / 60
    tst = (minutes + eot + 4 * lon) % 1440
    ha = tst / 4 - 180
    cz = math.sin(R(lat)) * math.sin(decl) + math.cos(R(lat)) * math.cos(decl) * math.cos(R(ha))
    zen = math.acos(max(-1.0, min(1.0, cz)))
    den = math.cos(R(lat)) * math.sin(zen)
    if abs(den) < 1e-9:
        az = 180.0 if lat > D(decl) else 0.0
    else:
        a = D(math.acos(max(-1.0, min(1.0, (math.sin(R(lat)) * math.cos(zen) - math.sin(decl)) / den))))
        az = (a + 180) % 360 if ha > 0 else (540 - a) % 360
    return az, 90 - D(zen)


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def parse_tz(s):
    m = s.strip()
    if m.upper() in ("Z", "UTC"):
        return timezone.utc, "+00:00"
    if m[0] in "+-":
        sign = -1 if m[0] == "-" else 1
        hh, mm = (m[1:].split(":") + ["0"])[:2]
        off = timedelta(hours=int(hh), minutes=int(mm)) * sign
        return timezone(off), m
    from zoneinfo import ZoneInfo
    return ZoneInfo(m), m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (local date)")
    ap.add_argument("--tz", required=True, help="offset like +03:00 or a zone name like Africa/Nairobi")
    ap.add_argument("--shadow-azimuth", type=float, help="direction the shadow points, degrees from true north")
    ap.add_argument("--tolerance", type=float, default=5, help="+/- degrees on the shadow direction (default 5)")
    ap.add_argument("--height", type=float, help="height of the object casting the shadow (any unit)")
    ap.add_argument("--shadow-length", type=float, help="length of its shadow (same unit as --height)")
    ap.add_argument("--ratio-tolerance", type=float, default=2, help="+/- degrees of sun elevation for the length ratio")
    ap.add_argument("--claimed", help="a claimed local time to test, HH:MM")
    ap.add_argument("--place", default="")
    ap.add_argument("--title", default="When could this shadow have been cast?")
    ap.add_argument("--source", default="", help="where the image came from, shown on the graphic")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.shadow_azimuth is None and not (a.height and a.shadow_length):
        sys.exit("give --shadow-azimuth, or --height and --shadow-length, or both")
    tz, tzlabel = parse_tz(a.tz)
    day = datetime.strptime(a.date, "%Y-%m-%d")
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    sun_az = None if a.shadow_azimuth is None else (a.shadow_azimuth + 180) % 360
    elev = None if not (a.height and a.shadow_length) else D(math.atan2(a.height, a.shadow_length))
    samples, hits = [], []
    for i in range(0, 1440):
        w = start + timedelta(minutes=i)
        az, el = sun_position(a.lat, a.lon, w)
        if i % 4 == 0:
            samples.append([i, round(az, 2), round(el, 2)])
        if el <= 0:
            continue
        ok = (sun_az is None or angle_diff(az, sun_az) <= a.tolerance) and (elev is None or abs(el - elev) <= a.ratio_tolerance)
        if ok:
            hits.append((i, az, el))
    windows = []
    for i, az, el in hits:
        if windows and i - windows[-1]["to"] <= 1:
            windows[-1]["to"] = i; windows[-1]["az2"], windows[-1]["el2"] = round(az, 1), round(el, 1)
        else:
            windows.append({"from": i, "to": i, "az1": round(az, 1), "el1": round(el, 1), "az2": round(az, 1), "el2": round(el, 1)})
    up = [s for s in samples if s[2] > 0]
    noon = max(samples, key=lambda s: s[2])
    claim = None
    if a.claimed:
        hh, mm = map(int, a.claimed.split(":"))
        az, el = sun_position(a.lat, a.lon, start + timedelta(hours=hh, minutes=mm))
        sh_az = (az + 180) % 360
        fits = el > 0 and (a.shadow_azimuth is None or angle_diff(sh_az, a.shadow_azimuth) <= a.tolerance) and \
            (elev is None or abs(el - elev) <= a.ratio_tolerance)
        claim = {"minute": hh * 60 + mm, "sun_az": round(az, 1), "sun_el": round(el, 1), "shadow_az": round(sh_az, 1),
                 "ratio": round(1 / math.tan(R(el)), 2) if el > 0.5 else None, "fits": fits,
                 "off_by": None if a.shadow_azimuth is None else round(angle_diff(sh_az, a.shadow_azimuth), 1)}
    utc_off = start.utcoffset().total_seconds() / 3600
    data = {"title": a.title, "place": a.place, "lat": a.lat, "lon": a.lon, "date": a.date, "tz": tzlabel, "utc_offset": utc_off,
            "shadow_az": a.shadow_azimuth, "tolerance": a.tolerance, "elev": None if elev is None else round(elev, 2),
            "height": a.height, "shadow_length": a.shadow_length, "ratio_tolerance": a.ratio_tolerance,
            "samples": samples, "windows": windows, "sunrise": up[0][0] if up else None, "sunset": up[-1][0] if up else None,
            "noon": noon[0], "noon_el": noon[2], "claim": claim, "source": a.source,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", page_json(data)).replace("__TITLE__", html.escape(a.title))
    dest = a.out or f"shadow-{a.date}.html"
    open(dest, "w", encoding="utf-8").write(page)
    hm = lambda m: f"{m // 60:02d}:{m % 60:02d}"
    print(f"wrote {dest}")
    if not windows:
        print("no time on this date fits the shadow you gave (check the direction, the date and the tolerance)")
    for w in windows:
        print(f"  fits {hm(w['from'])} to {hm(w['to'])} local ({tzlabel}): sun azimuth {w['az1']}-{w['az2']}, elevation {w['el1']}-{w['el2']}")
    if claim:
        print(f"  claimed {a.claimed}: sun at azimuth {claim['sun_az']}, elevation {claim['sun_el']}; shadows would point "
              f"{claim['shadow_az']} -> {'consistent' if claim['fits'] else 'does NOT fit'} the measured shadow")
    if (elev is not None and elev < 5) or any(w["el1"] < 3 or w["el2"] < 3 for w in windows):
        print("  note: the sun is near the horizon here; refraction is ignored, so treat this window as rough")
    return 0


if __name__ == "__main__":
    sys.exit(main())
