#!/usr/bin/env python3
"""Draw a geolocation evidence board from your own notes: a plan view with bearings to numbered
features, a sun and shadow check against a claimed time, a confidence checklist and score, and the
sources on the graphic.

Standard library only, and no network. The input is one JSON object:

  {
    "title": "From frame to coordinate, with the reasoning exposed",
    "subtitle": "Invented scene. A method demonstration.",
    "place": "Invented mid-latitude scene",
    "lat": 40.0, "lon": -75.0, "date": "2026-08-10", "tz": "-04:00",
    "claimed_time": "16:30",
    "shadow": {"azimuth_deg": 70, "tolerance_deg": 8, "height": 2.0, "length": 2.4},
    "features": [
      {"id": "F1", "label": "wall and factory roof", "bearing_deg": 55, "distance_m": 420, "match": true}
    ],
    "checks": [
      {"label": "Three independent features agree", "ok": true, "core": true},
      {"label": "Second sensor or source corroborates", "ok": false, "core": true}
    ],
    "sources": "Frame and features invented. Method: ..."
  }

The sun and shadow numbers are computed from `lat`, `lon`, `date`, `tz` and `claimed_time` with the
NOAA solar position equations, the same maths as shadow-diagram. The board states an inference: a
coordinate is a claim about a camera and a frame, not about a person's presence. This skill does not
name a person and does not publish a residence.
"""
import argparse
import html
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "board.html")
R, D = math.radians, math.degrees


def page_json(obj):
    """JSON for a <script> block. '<' is escaped so an input value can never close the tag."""
    return (json.dumps(obj, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def sun_position(lat, lon, when):
    """(azimuth, elevation) in degrees; azimuth clockwise from true north. `when` must be aware."""
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


def parse_tz(value):
    s = str(value or "").strip()
    if not s:
        raise ValueError("empty time zone")
    if s.upper() in ("Z", "UTC"):
        return timezone.utc, "UTC"
    if s[0] in "+-":
        sign = -1 if s[0] == "-" else 1
        parts = s[1:].split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        if hh > 14 or mm > 59:
            raise ValueError("offset out of range")
        return timezone(timedelta(hours=hh, minutes=mm) * sign), s
    try:
        from zoneinfo import ZoneInfo
    except ImportError as ex:
        raise ValueError("zone names need Python 3.9 or the tzdata package") from ex
    try:
        return ZoneInfo(s), s
    except Exception as ex:
        raise ValueError(f"unknown zone name {s!r}") from ex


def parse_hhmm(value):
    s = str(value or "").strip()
    if not s:
        raise ValueError("empty time")
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError("use HH:MM")
    hh, mm = int(parts[0]), int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("time out of range")
    return hh, mm


def number(value, default=None):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def load_board(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        sys.exit(f"{path}: expected one JSON object with features and checks")
    return data


def normalise(data):
    """Check the input and return the page data. Errors name the field that is wrong."""
    title = str(data.get("title") or "Geolocation evidence board").strip()
    subtitle = str(data.get("subtitle") or "").strip()
    place = str(data.get("place") or "").strip()
    sources = str(data.get("sources") or "").strip()

    raw_features = data.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        sys.exit("features: give a list with at least one feature")
    features = []
    for i, f in enumerate(raw_features, 1):
        if not isinstance(f, dict):
            sys.exit(f"features[{i}]: expected an object")
        label = str(f.get("label") or "").strip()
        if not label:
            sys.exit(f"features[{i}]: missing label")
        bearing = number(f.get("bearing_deg"))
        distance = number(f.get("distance_m"))
        if bearing is None or not (0 <= bearing < 360):
            sys.exit(f"features[{i}] ({label}): bearing_deg must be 0 to 359.9")
        if distance is None or distance <= 0:
            sys.exit(f"features[{i}] ({label}): distance_m must be greater than 0")
        features.append({
            "id": str(f.get("id") or f"F{i}").strip(),
            "label": label[:60],
            "bearing": round(bearing, 1),
            "distance": round(distance, 1),
            "match": f.get("match") is not False,
        })

    raw_checks = data.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        sys.exit("checks: give a list with at least one check")
    checks = []
    for i, c in enumerate(raw_checks, 1):
        if not isinstance(c, dict):
            sys.exit(f"checks[{i}]: expected an object")
        label = str(c.get("label") or "").strip()
        if not label:
            sys.exit(f"checks[{i}]: missing label")
        checks.append({"label": label[:90], "ok": c.get("ok") is True, "core": c.get("core") is True})

    core = [c for c in checks if c["core"]]
    basis = core if core else checks
    max_score = min(4, len(basis))
    score = min(max_score, sum(1 for c in basis if c["ok"]))
    gaps = sum(1 for c in basis if not c["ok"])

    sun = sun_check(data, features)

    return {
        "title": title,
        "subtitle": subtitle,
        "place": place,
        "sources": sources,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "features": features,
        "checks": checks,
        "score": score,
        "max": max_score,
        "gaps": gaps,
        "core_count": len(core),
        "sun": sun,
    }


def sun_check(data, features):
    """Return the sun and shadow panel data, or None when the place, date or time is missing."""
    keys = ("lat", "lon", "date", "tz", "claimed_time")
    if not all(data.get(k) not in (None, "") for k in keys):
        return {"missing": True}

    lat = number(data.get("lat"))
    lon = number(data.get("lon"))
    if lat is None or not (-90 <= lat <= 90):
        sys.exit("lat: give a latitude between -90 and 90")
    if lon is None or not (-180 <= lon <= 180):
        sys.exit("lon: give a longitude between -180 and 180")

    try:
        day = datetime.strptime(str(data.get("date")).strip(), "%Y-%m-%d")
        tz, tz_label = parse_tz(data.get("tz"))
        hh, mm = parse_hhmm(data.get("claimed_time"))
    except ValueError as ex:
        sys.exit(f"date, tz or claimed_time: {ex}")
    when = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
    az, el = sun_position(lat, lon, when)
    expected = (az + 180) % 360

    shadow = data.get("shadow") if isinstance(data.get("shadow"), dict) else {}
    tolerance = number(shadow.get("tolerance_deg"), 5.0)
    measured = number(shadow.get("azimuth_deg"))
    height = number(shadow.get("height"))
    length = number(shadow.get("length"))
    length_tol = number(shadow.get("length_tolerance_pct"), 15.0)

    out = {
        "missing": False, "lat": round(lat, 4), "lon": round(lon, 4),
        "date": day.strftime("%Y-%m-%d"), "tz": tz_label,
        "claimed": f"{hh:02d}:{mm:02d}", "azimuth": round(az, 1), "elevation": round(el, 1),
        "expected_shadow": round(expected, 1),
        "measured_shadow": None if measured is None else round(measured, 1),
        "shadow_tolerance": round(tolerance, 1),
        "shadow_diff": None, "shadow_fits": None,
        "height": height, "length": length, "length_tolerance_pct": round(length_tol, 1),
        "expected_length": None, "length_diff_pct": None, "length_fits": None,
        "below_horizon": el <= 0,
    }
    if measured is not None:
        if not (0 <= measured < 360):
            sys.exit("shadow.azimuth_deg: give a direction from 0 to 359.9")
        diff = angle_diff(measured, expected)
        out["shadow_diff"] = round(diff, 1)
        out["shadow_fits"] = bool(el > 0 and diff <= tolerance)
    if height and length and height > 0 and length > 0 and el > 0:
        expected_length = height / math.tan(R(el))
        out["expected_length"] = round(expected_length, 2)
        out["length_diff_pct"] = round(abs(length - expected_length) / expected_length * 100, 1)
        out["length_fits"] = bool(out["length_diff_pct"] <= length_tol)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", help="one JSON object with features, checks and, optionally, a place and time")
    ap.add_argument("--title", help="override the title in the input")
    ap.add_argument("--source", help="override the sources line in the input")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    data = normalise(load_board(a.input))
    if a.title:
        data["title"] = a.title
    if a.source:
        data["sources"] = a.source
    data["theme"] = a.theme
    data["input"] = os.path.basename(a.input)

    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = (page.replace("/*__DATA__*/null", page_json(data))
                .replace("__TITLE__", html.escape(data["title"])))
    dest = a.out or os.path.splitext(a.input)[0] + "-board.html"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"wrote {dest} ({os.path.getsize(dest) // 1024} KB)")
    print(f"  {len(data['features'])} features, evidence score {data['score']} / {data['max']}")
    if data["sun"].get("missing"):
        print("  no sun check: add lat, lon, date, tz and claimed_time to test a time")
    elif data["sun"]["below_horizon"]:
        print(f"  sun check: below the horizon at {data['sun']['claimed']}; no shadow to compare")
    elif data["sun"]["shadow_fits"] is True:
        print(f"  sun check: measured shadow {data['sun']['measured_shadow']} deg differs from the "
              f"expected {data['sun']['expected_shadow']} deg by {data['sun']['shadow_diff']} deg, within "
              f"the {data['sun']['shadow_tolerance']} deg tolerance")
    elif data["sun"]["shadow_fits"] is False:
        print(f"  sun check: measured shadow {data['sun']['measured_shadow']} deg differs from the "
              f"expected {data['sun']['expected_shadow']} deg by {data['sun']['shadow_diff']} deg, outside "
              f"the {data['sun']['shadow_tolerance']} deg tolerance")
    if data["gaps"]:
        print(f"  {data['gaps']} core check(s) not met; say so when you publish")
    if not data["sources"]:
        print("note: no sources given; say where the frame, the imagery and the coordinates came from")
    print("  note: a coordinate is not a person's presence. This board names no one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())