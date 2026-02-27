#!/usr/bin/env python3
"""
Validate (and optionally auto-fix) non-polygon town coordinates against
OpenStreetMap Nominatim — the same geocoding data that powers the Leaflet
street view map tiles.

HOW IT WORKS
------------
Nominatim is the geocoding API behind OpenStreetMap — the same dataset rendered
by the Leaflet street-view layer. Querying it for each city name gives us the
"golden" coordinates as the map itself would show them, so any significant
difference (> THRESHOLD_KM) flags a mismatch between the stored pin and what
the map actually renders at that location.

USAGE
-----
    python3 validate_coords.py            # validate only, report mismatches
    python3 validate_coords.py --apply    # also patch index.html with OSM coords

Nominatim requires a 1 req/sec rate limit (enforced automatically).
The script only checks non-polygon locations because polygon cities use
boundary data for scoring anyway and already have visual coverage.

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

# ── towns to skip (have polygon mapping, already validated) ──────────────────
POLYGON_TOWNS = {
    "Afula","Akko","Arad","Arrabe","Ashdod","Ashkelon","Baqa al-Gharbiyye",
    "Bat Yam","Beer Sheva","Beit She'an","Beit Shemesh","Binyamina","Bnei Brak",
    "Daliyat al-Karmel","Dimona","Eilat","Even Yehuda","Gan Yavne","Ganei Tikva",
    "Gedera","Giv'at Shmuel","Givatayim","Hadera","Haifa","Herzliya",
    "Hod HaSharon","Holon","Isfiya","Jisr az-Zarqa","Kafr Qasim","Kafr Qara",
    "Kafr Yasif","Karmiel","Katzrin","Kfar Saba","Kiryat Ata","Kiryat Bialik",
    "Kiryat Motzkin","Kiryat Ono","Kiryat Shmona","Kiryat Yam","Lod",
    "Ma'ale Adumim","Ma'alot-Tarshiha","Majd al-Krum","Mevaseret Zion","Metula",
    "Migdal HaEmek","Mitzpe Ramon","Modi'in","Nazareth","Nes Ziona","Nesher",
    "Netanya","Netivot","Nof HaGalil","Nazareth Illit","Ofakim","Omer",
    "Or Akiva","Or Yehuda","Pardes Hanna","Petah Tikva","Qalansawe",
    "Qiryat Tiv'on","Ra'anana","Rahat","Ramat Gan","Ramat HaSharon","Ramla",
    "Rehovot","Rishon LeZion","Rosh HaAyin","Safed","Sakhnin","Sderot",
    "Shfar'am","Shoham","Tamra","Tel Aviv","Tel Mond","Tiberias","Tira",
    "Tirat Carmel","Umm al-Fahm","Yavne","Yavne'el","Yehud","Yeroham",
    "Yoqne'am Illit","Zichron Ya'akov","Daburiyya","Elad","Hazor HaGlilit",
    "Kafr Kanna","Kfar Kama","Kfar Manda","Kfar Shmaryahu","Kfar Tavor",
    "Kfar Yona","Kiryat Ekron","Majdal Shams","Migdal","Peki'in","Rame",
    "Reina","Savyon","Shlomi","Yesud HaMa'ala",
}

# ── OSM search aliases for tricky names ──────────────────────────────────────
OSM_ALIASES = {
    "Sha'ar HaGolan":     "Sha'ar HaGolan",
    "Mitzpe Netofa":      "Mitzpe Netofa",
    "Birya":              "Biriya",
    "Buq'ata":            "Buq'ata",
    "Kochav Yair":        "Kochav Yair-Tzur Yigal",
    "Nir David":          "Nir David (Tel Amal)",
    "Meona":              "Me'ona",
}

# ── interchanges / junctions to skip (no OSM city record) ───────────────────
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

THRESHOLD_KM = 3.0          # report/apply if more than this far from OSM
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
                return float(results[0]["lat"]), float(results[0]["lon"]), results[0].get("display_name","")
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
    # Match the exact lat/lng for this name to avoid false replacements
    old_snippet = f'name:"{name}", lat:{old_lat}, lng:{old_lng}'
    new_snippet = f'name:"{name}", lat:{new_lat:.4f}, lng:{new_lng:.4f}'
    if old_snippet not in content:
        # Try without spaces (formatting may vary)
        old_snippet = re.sub(r'\s+', '', old_snippet)
        pattern = re.compile(
            r'(name:"' + re.escape(name) + r'",\s*lat:)' +
            re.escape(str(old_lat)) + r'(,\s*lng:)' + re.escape(str(old_lng))
        )
        new_content = pattern.sub(
            lambda m: m.group(1) + f'{new_lat:.4f}' + m.group(2) + f'{new_lng:.4f}',
            content, count=1
        )
    else:
        new_content = content.replace(old_snippet, new_snippet, 1)
    if new_content == content:
        return False  # nothing changed
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

def main():
    import os
    apply_mode = "--apply" in sys.argv
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

    towns = parse_towns(html_path)
    non_polygon = [(n, la, ln) for n, la, ln in towns
                   if n not in POLYGON_TOWNS and n not in SKIP_NAMES]

    mode_label = " (APPLY MODE — will patch index.html)" if apply_mode else " (dry run — use --apply to patch)"
    print(f"Validating {len(non_polygon)} non-polygon locations against OSM Nominatim...{mode_label}\n")
    print(f"{'Location':<30} {'Stored':>22} {'OSM':>22} {'Diff km':>8}  Status")
    print("-" * 100)

    applied = []
    flagged = []
    ok_count = 0

    for name, stored_lat, stored_lng in non_polygon:
        time.sleep(1.1)   # Nominatim rate limit: max 1 req/sec
        osm_lat, osm_lng, display = nominatim_lookup(name)

        if osm_lat is None:
            print(f"  {'  ' + name:<28} ({stored_lat:.4f},{stored_lng:.4f})  {'':>22} {'?':>8}  LOOKUP FAILED: {display}")
            continue

        dist = haversine_km(stored_lat, stored_lng, osm_lat, osm_lng)
        stored_str = f"({stored_lat:.4f},{stored_lng:.4f})"
        osm_str    = f"({osm_lat:.4f},{osm_lng:.4f})"

        if dist <= THRESHOLD_KM:
            print(f"  {name:<28} {stored_str:>22} {osm_str:>22} {dist:>7.1f}km  OK")
            ok_count += 1
        else:
            if apply_mode:
                patched = apply_fix(html_path, name, stored_lat, stored_lng, osm_lat, osm_lng)
                status = "PATCHED" if patched else "PATCH FAILED"
                applied.append((name, stored_lat, stored_lng, osm_lat, osm_lng, dist))
            else:
                status = "*** CHECK ***"
                flagged.append((name, stored_lat, stored_lng, osm_lat, osm_lng, dist, display))
            print(f"  {name:<28} {stored_str:>22} {osm_str:>22} {dist:>7.1f}km  {status}")

    print("\n" + "=" * 100)

    if apply_mode:
        print(f"\nSUMMARY: {ok_count} already correct, {len(applied)} patched in index.html\n")
        if applied:
            print("PATCHED LOCATIONS:")
            for name, slat, slng, olat, olng, dist in sorted(applied, key=lambda x: -x[5]):
                print(f"  {name}: ({slat}, {slng}) → ({olat:.4f}, {olng:.4f})  [{dist:.1f} km corrected]")
    else:
        print(f"\nSUMMARY: {ok_count} OK, {len(flagged)} flagged (>{THRESHOLD_KM} km from OSM)")
        print("Run with --apply to automatically patch all flagged coords in index.html\n")
        if flagged:
            print("FLAGGED LOCATIONS:")
            for name, slat, slng, olat, olng, dist, display in sorted(flagged, key=lambda x: -x[5]):
                print(f"  {name}")
                print(f"    Stored:  {slat}, {slng}")
                print(f"    OSM:     {olat:.4f}, {olng:.4f}  ({dist:.1f} km off)")
                print(f"    OSM name: {display[:80]}")
                print()

if __name__ == "__main__":
    main()
