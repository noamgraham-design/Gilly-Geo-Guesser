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
    python3 validate_coords.py                          # dry run — all towns via Nominatim
    python3 validate_coords.py --apply                  # patch index.html via Nominatim
    python3 validate_coords.py --unmatched-only         # dry run — only previously-unmatched towns via Overpass name:en
    python3 validate_coords.py --unmatched-only --apply # patch unmatched towns using Overpass results

The --unmatched-only flag targets the 38 towns whose Nominatim results were
> 3 km off (wrong place returned).  Instead of Nominatim free-text search it
uses the Overpass API to find OSM places whose English name (name:en tag)
matches — the same data rendered by the CartoDB Positron English map layer.

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

# ── Overpass name:en aliases — English names that differ in OSM ───────────────
OVERPASS_ALIASES = {
    "Masade":          ["Mas'ade", "Mas'ada"],
    "Givat Ze'ev":     ["Giv'at Ze'ev", "Givat Zeev"],
    "Modi'in":         ["Modi'in-Maccabim-Re'ut", "Modiin"],
    "Kiryat Arba":     ["Qiryat Arba"],
    "Shfar'am":        ["Shefa-'Amr", "Shefar'am"],
    "Mazra'a":         ["Mazra'a ash-Sharqiyya"],
    "Kisra-Sumei":     ["Kisra-Sumi'a"],
    "Kfar Vradim":     ["Kefar Weradim"],
    "Kochav Yair":     ["Kokhav Ya'ir", "Kokhav Ya'ir – Tzur Yig'al"],
    "Tuba-Zangariyye": ["Tuba-Zangariyya"],
    "Rehasim":         ["Rekhasim"],
    "Ilabun":          ["Eilabun", "'Ilabun"],
    "Kadima-Zoran":    ["Kadima Zoran"],
    "Yavne'el":        ["Yavneel"],
    "Neve Shalom":     ["Neve Shalom/Wahat al-Salam"],
    "Buq'ata":         ["Buqata"],
    "Tayibe":          ["at-Tayibe"],
    "Tel Sheva":       ["Tel as-Sabi"],
    "Laqiya":          ["Laqye"],
    "Hurfeish":        ["Ḥurfeish"],
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

# ── Previously unmatched towns (> 3 km Nominatim delta) ──────────────────────
UNMATCHED_TOWNS = {
    "Masade", "Ariel", "Givat Ze'ev", "Julis", "Oranit", "Efrat",
    "Kiryat Arba", "Modi'in", "Jericho", "Mazra'a", "Shfar'am",
    "Tel Sheva", "Hurfeish", "Sajur", "Yanuh-Jat", "Zarzir",
    "Sha'ab", "Kisra-Sumei", "Kfar Vradim", "Ramot Naftali",
    "Kochav Yair", "Mitzpe Netofa", "Kabul", "Ma'ale Adumim",
    "Zemer", "Laqiya", "Ilut", "Tayibe", "Mishmar HaNegev",
    "Buq'ata", "Yirka", "Yavne'el", "Neve Shalom", "Rehasim",
    "Tuba-Zangariyye", "Ilabun", "Kadima-Zoran", "Netanya",
}

# ── Bounding box for Israel + occupied territories (S,W,N,E) ─────────────────
ISRAEL_BBOX = "29.0,34.0,33.5,36.0"

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── Overpass API helpers (query OSM name:en — same data as English map layer) ─

def _element_coords(el):
    """Extract (lat, lng) from an Overpass element (node, way center, or relation center)."""
    if "center" in el:
        return float(el["center"]["lat"]), float(el["center"]["lon"])
    return float(el["lat"]), float(el["lon"])

def _pick_closest(elements, stored_lat, stored_lng):
    """When Overpass returns multiple results, pick the one closest to stored coords."""
    if not stored_lat or not stored_lng or len(elements) == 1:
        return elements[0]
    best, best_dist = elements[0], float("inf")
    for el in elements:
        try:
            lat, lng = _element_coords(el)
            dist = haversine_km(stored_lat, stored_lng, lat, lng)
            if dist < best_dist:
                best, best_dist = el, dist
        except (KeyError, TypeError):
            continue
    return best

def overpass_lookup(name, stored_lat=None, stored_lng=None):
    """
    Search the OSM Overpass API for a place whose English name (name:en tag)
    matches.  This queries the same OSM data rendered by the CartoDB Positron
    English map layer used in the game.

    Search order: name:en → int_name → name, trying aliases for each tag.
    """
    candidates = [name] + OVERPASS_ALIASES.get(name, [])
    last_err = ""

    for tag in ("name:en", "int_name", "name"):
        for candidate in candidates:
            query = (
                f'[out:json][timeout:15];'
                f'('
                f'node["place"]["{tag}"="{candidate}"]({ISRAEL_BBOX});'
                f'way["place"]["{tag}"="{candidate}"]({ISRAEL_BBOX});'
                f'relation["place"]["{tag}"="{candidate}"]({ISRAEL_BBOX});'
                f');'
                f'out center;'
            )
            data = urllib.parse.urlencode({"data": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://overpass-api.de/api/interpreter",
                data=data,
                headers={"User-Agent": "GillyGeoGuesser-validator/1.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    result = json.loads(resp.read())
                    elements = result.get("elements", [])
                    if elements:
                        best = _pick_closest(elements, stored_lat, stored_lng)
                        lat, lng = _element_coords(best)
                        tags = best.get("tags", {})
                        display = tags.get("name:en", tags.get("name", candidate))
                        return lat, lng, f"{display} [matched {tag}]"
            except Exception as e:
                last_err = str(e)
            time.sleep(1.5)   # Overpass rate limit

    return None, None, f"No Overpass match{': ' + last_err if last_err else ''}"

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
    unmatched_only = "--unmatched-only" in sys.argv
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

    all_towns = parse_towns(html_path)

    if unmatched_only:
        towns = [(n, la, ln) for n, la, ln in all_towns if n in UNMATCHED_TOWNS]
        method = "Overpass name:en"
    else:
        towns = [(n, la, ln) for n, la, ln in all_towns if n not in SKIP_NAMES]
        method = "Nominatim"

    mode_label = " (APPLY MODE — patching index.html)" if apply_mode else " (dry run — use --apply to patch)"
    print(f"Checking {len(towns)} towns via {method}...{mode_label}\n")
    print(f"{'Location':<30} {'Stored':>22} {method+' coords':>22} {'Diff km':>8}  Status")
    print("-" * 110)

    patched_list = []
    failed_list = []

    for name, stored_lat, stored_lng in towns:
        if unmatched_only:
            osm_lat, osm_lng, display = overpass_lookup(name, stored_lat, stored_lng)
        else:
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
            status = f"{dist:.1f}km delta  ({display})"

        print(f"  {name:<28} {stored_str:>22} {osm_str:>22} {dist:>7.1f}km  {status}")

    print("\n" + "=" * 110)

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
        print(f"\nSUMMARY: {len(towns)} towns checked via {method}, {len(failed_list)} lookup failures")
        if unmatched_only:
            print("Run with --unmatched-only --apply to patch these coordinates.\n")
        else:
            print("Run with --apply to sync all coordinates to OSM values.\n")
        if failed_list:
            print("LOOKUP FAILURES:")
            for name, err in failed_list:
                print(f"  {name}: {err}")

if __name__ == "__main__":
    main()
