#!/usr/bin/env python3
"""
Sync OSM coordinates from israel_localities_with_coords.json into towns.js,
but only for towns that have NO polygon assigned in CITY_POLYGON_SLUG (index.html).

USAGE
-----
    python3 sync_towns_coords.py       # dry run — print changes, don't write
    python3 sync_towns_coords.py --apply  # write updated towns.js
"""

import sys
import re
import json
import os
import math

MAX_DISTANCE_KM = 10  # skip updates where new coord is farther than this from old

BASE = os.path.dirname(os.path.abspath(__file__))
TOWNS_FILE      = os.path.join(BASE, "towns.js")
INDEX_FILE      = os.path.join(BASE, "index.html")
LOCALITIES_FILE = os.path.join(BASE, "israel_localities_with_coords.json")

apply_mode = "--apply" in sys.argv


# ── 1. Extract polygon towns from CITY_POLYGON_SLUG in index.html ────────────
with open(INDEX_FILE, encoding="utf-8") as f:
    index_text = f.read()

slug_block_match = re.search(r'const CITY_POLYGON_SLUG\s*=\s*\{([^}]+)\}', index_text, re.DOTALL)
if not slug_block_match:
    sys.exit("ERROR: Could not find CITY_POLYGON_SLUG in index.html")

polygon_towns = set(re.findall(r'"([^"]+)"\s*:', slug_block_match.group(1)))
print(f"Polygon towns ({len(polygon_towns)}): skipping these")


# ── 2. Build lookup from israel_localities_with_coords.json ──────────────────
with open(LOCALITIES_FILE, encoding="utf-8") as f:
    localities = json.load(f)

by_eng = {}
by_heb = {}
for entry in localities:
    if "coord" not in entry:
        continue  # no coordinates — skip
    coord = entry["coord"]
    eng = entry.get("English Name", "").strip()
    heb = entry.get("Hebrew Name", "").strip()
    if eng:
        by_eng[eng] = coord
    if heb:
        by_heb[heb] = coord

print(f"Localities with coords: {len(by_eng)} by English name, {len(by_heb)} by Hebrew name\n")


# ── 3. Parse towns.js for name / nameHe / lat / lng ──────────────────────────
# Each line looks like: { name:"Foo",  lat:31.1234, lng:35.5678, ...nameHe:"פו"... }
ENTRY_RE = re.compile(
    r'name:"([^"]+)"[^}]*?lat:([\d.]+)[^}]*?lng:([\d.]+)[^}]*?nameHe:"([^"]+)"'
)

with open(TOWNS_FILE, encoding="utf-8") as f:
    towns_text = f.read()

towns = ENTRY_RE.findall(towns_text)  # list of (name, lat, lng, nameHe)
print(f"Towns in towns.js: {len(towns)}\n")
print(f"{'Town':<30} {'Hebrew':<20} {'Old coords':>26}  {'New coords':>26}  Result")
print("-" * 115)


# ── 4. For each polygon-less town, find a coord match and replace ─────────────
LAT_LNG_RE = re.compile(
    r'(name:"(?P<name>[^"]+)",\s*lat:)(?P<lat>[\d.]+)(,\s*lng:)(?P<lng>[\d.]+)'
)

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


updated          = 0
skipped_polygon  = 0
no_match         = 0
suspicious       = 0

def do_replace(text, name, new_lat, new_lng):
    """Replace lat/lng for the given name in towns.js text. Returns new text."""
    pattern = re.compile(
        r'(name:"' + re.escape(name) + r'",\s*lat:)([\d.]+)(,\s*lng:)([\d.]+)'
    )
    new_text, n = pattern.subn(
        lambda m: m.group(1) + str(new_lat) + m.group(3) + str(new_lng),
        text
    )
    return new_text, n

for name, lat_str, lng_str, nameHe in towns:
    old_lat = float(lat_str)
    old_lng = float(lng_str)

    if name in polygon_towns:
        skipped_polygon += 1
        continue

    # Try English name first, then Hebrew
    coord = by_eng.get(name) or by_heb.get(nameHe)

    if coord is None:
        print(f"  {name:<28} {nameHe:<20} ({old_lat:.4f}, {old_lng:.4f})  {'':>26}  NO MATCH")
        no_match += 1
        continue

    new_lat = round(coord["lat"], 4)
    new_lng = round(coord["lng"], 4)
    old_str = f"({old_lat:.4f}, {old_lng:.4f})"
    new_str = f"({new_lat:.4f}, {new_lng:.4f})"

    if new_lat == old_lat and new_lng == old_lng:
        print(f"  {name:<28} {nameHe:<20} {old_str:>26}  {'(unchanged)':>26}  SAME")
        continue

    dist_km = haversine_km(old_lat, old_lng, new_lat, new_lng)
    if dist_km > MAX_DISTANCE_KM:
        print(f"  {name:<28} {nameHe:<20} {old_str:>26}  {new_str:>26}  SUSPICIOUS ({dist_km:.0f} km)")
        suspicious += 1
        continue

    print(f"  {name:<28} {nameHe:<20} {old_str:>26}  {new_str:>26}  UPDATE ({dist_km:.1f} km)")
    towns_text, n = do_replace(towns_text, name, new_lat, new_lng)
    if n == 0:
        print(f"    WARNING: regex replacement matched 0 times for '{name}'")
    else:
        updated += 1

print("\n" + "=" * 115)
print(f"\nSUMMARY")
print(f"  Total towns      : {len(towns)}")
print(f"  Has polygon      : {skipped_polygon}  (skipped — polygon handles scoring)")
print(f"  Updated          : {updated}")
print(f"  No match         : {no_match}  (not found in israel_localities_with_coords.json)")
print(f"  Suspicious       : {suspicious}  (>{MAX_DISTANCE_KM} km jump — likely bad OSM match, skipped)")
print(f"  Unchanged        : {len(towns) - skipped_polygon - updated - no_match - suspicious}")

if apply_mode:
    with open(TOWNS_FILE, "w", encoding="utf-8") as f:
        f.write(towns_text)
    print(f"\nWrote updated {TOWNS_FILE}")
else:
    print(f"\nDry run — run with --apply to write towns.js")
