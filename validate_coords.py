#!/usr/bin/env python3
"""
Sync all town coordinates in index.html to OpenStreetMap Nominatim values —
the same geocoding data that powers the Leaflet street view map tiles.

HOW IT WORKS
------------
Nominatim is the geocoding API behind OpenStreetMap — the same dataset rendered
by the Leaflet street-view layer. Querying it for each city name returns the
canonical coordinates for what the map actually shows at that location.
Running with --apply replaces every stored lat/lng with the OSM value,
so answer pins land exactly where the street-view map renders each place.

USAGE
-----
    python3 validate_coords.py            # dry run — show stored vs OSM for all towns
    python3 validate_coords.py --apply    # patch index.html with OSM coords for all towns

Nominatim requires a 1 req/sec rate limit (enforced automatically).
Interchanges/junctions are skipped — they have no OSM city record.

REQUIREMENTS
------------
Python 3.7+, standard library only (urllib, re, json, math, time, sys).
Outbound HTTPS access to nominatim.openstreetmap.org on port 443.
"""

import re
import sys
import time
import math
import json
import urllib.request
import urllib.parse

# ── OSM search aliases for names that need rewording to match OSM ─────────────
OSM_ALIASES = {
    "Sha'ar HaGolan":  "Sha'ar HaGolan",
    "Mitzpe Netofa":   "Mitzpe Netofa",
    "Birya":           "Biriya",
    "Buq'ata":         "Buq'ata",
    "Kochav Yair":     "Kochav Yair-Tzur Yigal",
    "Nir David":       "Nir David (Tel Amal)",
    "Meona":           "Me'ona",
}

# ── interchanges / junctions — no OSM city record, skip entirely ──────────────
SKIP_NAMES = {
    "Gesher HaYarkon Interchange","Sha'ar HaGai Interchange","Qasem Interchange",
    "Golani Interchange","Yokneam Interchange","Glilot Interchange",
    "Hemed Interchange","Eyal Interchange","Plugot Interchange",
    "Zohar Interchange","Lehavim Interchange","Afula Interchange",
    "Haifa North Interchange","Gan Shmuel Interchange","Caesarea Interchange",
    "Megiddo Interchange","Geha Interchange","Latrun Interchange",
    "Beer Sheva North Interchange","Kfar Netter Interchange",
    "Mahanayim Interchange","Ben Gurion Interchange","Bilu Interchange",
    "HaSharon Interchange","Ein Tut Interchange","Morasha Interchange",
    "Ramat Yishay Interchange","Nahshonim Interchange","Tzomet HaGader Interchange",
}

ISRAEL_COUNTRY_CODES = "IL,PS"  # include West Bank (PS)

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def nominatim_lookup(name, country_codes=ISRAEL_COUNTRY_CODES):
    query = OSM_ALIASES.get(name, name)
    params = urllib.parse.urlencode({
        "q": f"{query}, Israel",
        "format": "json",
        "limit": 3,
        "countrycodes": country_codes,
        "addressdetails": 0,
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "GillyGeoGuesser-validator/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read())
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"]), results[0].get("display_name", "")
    except Exception as e:
        return None, None, f"ERROR: {e}"
    return None, None, "No result"

def parse_towns(html_path):
    with open(html_path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r'\{\s*name:"([^"]+)",\s*lat:([\d.]+),\s*lng:([\d.]+)')
    return [(m.group(1), float(m.group(2)), float(m.group(3)))
            for m in pattern.finditer(content)]

def apply_fix(html_path, name, old_lat, old_lng, new_lat, new_lng):
    """Patch index.html, replacing the stored coords for `name` with OSM values."""
    with open(html_path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r'(name:"' + re.escape(name) + r'",\s*lat:)' +
        re.escape(str(old_lat)) + r'(,\s*lng:)' + re.escape(str(old_lng))
    )
    new_content = pattern.sub(
        lambda m: m.group(1) + f'{new_lat:.4f}' + m.group(2) + f'{new_lng:.4f}',
        content, count=1
    )
    if new_content == content:
        return False
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

def main():
    import os
    apply_mode = "--apply" in sys.argv
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

    all_towns = parse_towns(html_path)
    towns = [(n, la, ln) for n, la, ln in all_towns if n not in SKIP_NAMES]

    mode_label = " (APPLY MODE — patching index.html)" if apply_mode else " (dry run — use --apply to patch)"
    print(f"Syncing {len(towns)} towns to OSM Nominatim coords...{mode_label}\n")
    print(f"{'Location':<30} {'Stored':>22} {'OSM':>22} {'Diff km':>8}  Status")
    print("-" * 100)

    patched_list = []
    failed_list = []

    for name, stored_lat, stored_lng in towns:
        time.sleep(1.1)   # Nominatim rate limit: max 1 req/sec
        osm_lat, osm_lng, display = nominatim_lookup(name)

        stored_str = f"({stored_lat:.4f},{stored_lng:.4f})"

        if osm_lat is None:
            print(f"  {name:<28} {stored_str:>22} {'':>22} {'?':>8}  LOOKUP FAILED: {display}")
            failed_list.append((name, display))
            continue

        dist = haversine_km(stored_lat, stored_lng, osm_lat, osm_lng)
        osm_str = f"({osm_lat:.4f},{osm_lng:.4f})"

        if apply_mode:
            patched = apply_fix(html_path, name, stored_lat, stored_lng, osm_lat, osm_lng)
            status = "PATCHED" if patched else "unchanged"
            if patched:
                patched_list.append((name, stored_lat, stored_lng, osm_lat, osm_lng, dist))
        else:
            status = f"{dist:.1f}km delta"

        print(f"  {name:<28} {stored_str:>22} {osm_str:>22} {dist:>7.1f}km  {status}")

    print("\n" + "=" * 100)

    if apply_mode:
        print(f"\nSUMMARY: {len(patched_list)} patched, {len(towns) - len(patched_list) - len(failed_list)} already matched, {len(failed_list)} lookup failures\n")
        if patched_list:
            print("PATCHED (sorted by correction size):")
            for name, slat, slng, olat, olng, dist in sorted(patched_list, key=lambda x: -x[5]):
                print(f"  {name:<30} ({slat}, {slng}) → ({olat:.4f}, {olng:.4f})  [{dist:.1f} km]")
        if failed_list:
            print("\nLOOKUP FAILURES (not patched):")
            for name, err in failed_list:
                print(f"  {name}: {err}")
    else:
        print(f"\nSUMMARY: {len(towns)} towns checked, {len(failed_list)} lookup failures")
        print("Run with --apply to sync all coordinates to OSM values.\n")
        if failed_list:
            print("LOOKUP FAILURES:")
            for name, err in failed_list:
                print(f"  {name}: {err}")

if __name__ == "__main__":
    main()
