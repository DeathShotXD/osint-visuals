#!/usr/bin/env python3
"""Writes the invented example inputs in examples/. Nothing here is real: the vessels, names and positions are
made up to show what the skills flag. Run: python3 tools/make_demo_data.py"""
import csv
import math
import os
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leg(a, b, t0, hours, step_min=20):
    n = int(hours * 60 / step_min)
    return [(t0 + timedelta(minutes=step_min * i), a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def tankers():
    """Two invented tankers in the Gulf of Oman: one goes dark, the two meet, then one 'jumps' (a spoofed fix)."""
    t0 = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    meet = (24.62, 58.30)
    # MERIDIAN STAR: sails north-east, goes dark for 31 h around the meeting, reappears heading south
    a = leg((23.62, 58.95), (24.60, 58.33), t0, 20)                 # last report 3 km from the meeting point
    dark_from = a[-1][0]
    b = leg((meet[0] + 0.002, meet[1] + 0.004), (meet[0] + 0.003, meet[1] + 0.006), dark_from + timedelta(hours=31), 3, 30) + \
        leg((meet[0] + 0.003, meet[1] + 0.006), (24.10, 58.92), dark_from + timedelta(hours=34, minutes=20), 12)   # reappears alongside
    jump_t = b[-1][0] + timedelta(minutes=20)
    b2 = [(jump_t, 22.40, 59.95)]                       # one impossible fix
    c = leg((24.08, 58.95), (23.40, 59.40), jump_t + timedelta(minutes=20), 16)
    m = [("MERIDIAN STAR", *p) for p in a + b + b2 + c]
    # KESTREL BAY: comes in from the west, waits at the meeting point (transmitting), leaves west
    k = leg((25.05, 56.95), meet, t0 + timedelta(hours=8), 26) + \
        leg((meet[0] + 0.004, meet[1] + 0.003), (meet[0] + 0.006, meet[1] + 0.005), t0 + timedelta(hours=34, minutes=20), 21, 30) + \
        leg((meet[0] + 0.006, meet[1] + 0.005), (25.20, 56.80), t0 + timedelta(hours=55, minutes=50), 20)
    k = [("KESTREL BAY", *p) for p in k]
    rows = sorted(m + k, key=lambda r: r[1])
    path = os.path.join(ROOT, "examples", "track", "demo-tankers.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["vessel", "timestamp", "lat", "lon"])
        for name, t, la, lo in rows:
            w.writerow([name, t.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{la:.5f}", f"{lo:.5f}"])
    print("wrote", path, len(rows), "rows")


if __name__ == "__main__":
    tankers()
