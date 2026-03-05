#!/usr/bin/env python3
"""
Fetch OSM coordinates for every locality in israel_localities.json using
the Hebrew name (name:he OSM tag / Nominatim Hebrew query).

HOW IT WORKS
------------
For each locality the script tries two methods in order:

  1. Nominatim free-text search with the Hebrew name, bounded to the
     Israel + West Bank bounding box.  This covers the vast majority of
     populated places that exist in OSM with a name:he tag.

  2. Overpass API fallback — queries OSM directly for nodes/ways/relations
     whose name:he tag exactly matches the Hebrew name.  Used when
     Nominatim returns nothing inside the bounding box.

Matched entries get:  "coord": {"lat": <float>, "lng": <float>}
Unmatched entries get: "coord": "UNMATCHED"   <- easy to grep/filter

USAGE
-----
    python3 fetch_osm_coordinates.py                # dry run — print results only
    python3 fetch_osm_coordinates.py --apply        # write updated israel_localities.json
    python3 fetch_osm_coordinates.py --resume       # skip entries that already have coord
    python3 fetch_osm_coordinates.py --jewish-only  # skip obvious Arab localities
    python3 fetch_osm_coordinates.py --apply --resume   # apply + skip already-fetched

REQUIREMENTS
------------
Python 3.7+, standard library only (urllib, json, math, time, sys, os).
Outbound HTTPS access to nominatim.openstreetmap.org and overpass-api.de.
Nominatim rate limit: 1 req/sec (enforced automatically).
"""

import sys
import os
import time
import json
import math
import urllib.request
import urllib.parse
import urllib.error

# ── Israel + West Bank bounding box ─────────────────────────────────────────
# Nominatim viewbox format: left(lon_min), top(lat_max), right(lon_max), bottom(lat_min)
NOMINATIM_VIEWBOX = "34.0,33.5,36.0,29.0"
# Overpass format: S,W,N,E
OVERPASS_BBOX = "29.0,34.0,33.5,36.0"
COUNTRY_CODES = "il,ps"

LOCALITIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "israel_localities.json")
LOG_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_osm_coordinates.log")
USER_AGENT      = "GillyGeoGuesser-coord-fetcher/1.0"

# ── Arab-locality heuristics for --jewish-only ───────────────────────────────
ARAB_HEB_MARKERS  = ["(שבט)"]                              # Bedouin tribe suffix
ARAB_HEB_PREFIXES = ["אבו "]                               # Abu...
ARAB_ENG_PREFIXES = ["Abu ", "Al ", "Al-", "Kafr ", "Bir ", "Umm ", "Um "]


class TeeWriter:
    """Write to both stdout and a log file simultaneously."""
    def __init__(self, logfile, original_stdout):
        self.logfile = logfile
        self.stdout  = original_stdout
    def write(self, text):
        self.stdout.write(text)
        self.logfile.write(text)
    def flush(self):
        self.stdout.flush()
        self.logfile.flush()


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def is_arab(entry):
    heb = entry.get("Hebrew Name", "")
    eng = entry.get("English Name", "")
    return (
        any(m in heb for m in ARAB_HEB_MARKERS) or
        any(heb.startswith(p) for p in ARAB_HEB_PREFIXES) or
        any(eng.startswith(p) for p in ARAB_ENG_PREFIXES)
    )


def nominatim_lookup(hebrew_name):
    """
    Query Nominatim with the Hebrew name, bounded to Israel + West Bank.
    Returns (lat, lng, display_name) or (None, None, error_msg).
    Retries up to 4 times on 429/504 with exponential backoff (2s, 4s, 8s, 16s).
    """
    params = urllib.parse.urlencode({
        "q":               hebrew_name,
        "format":          "json",
        "limit":           5,
        "countrycodes":    COUNTRY_CODES,
        "accept-language": "he",
        "viewbox":         NOMINATIM_VIEWBOX,
        "bounded":         1,
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                results = json.loads(resp.read())
                if results:
                    # Prefer place-class results; fall back to first result
                    place_results = [r for r in results if r.get("class") == "place"]
                    best = place_results[0] if place_results else results[0]
                    return float(best["lat"]), float(best["lon"]), best.get("display_name", "")
                return None, None, "No result"
        except urllib.error.HTTPError as e:
            last_err = str(e)
            if e.code in (429, 504) and attempt < 3:
                wait = 2 * (2 ** attempt)  # 2s, 4s, 8s, 16s
                time.sleep(wait)
                continue
            break
        except Exception as e:
            last_err = str(e)
            break
    return None, None, f"ERROR: {last_err}"


def _element_coords(el):
    """Extract (lat, lng) from an Overpass element."""
    if "center" in el:
        return float(el["center"]["lat"]), float(el["center"]["lon"])
    return float(el["lat"]), float(el["lon"])


def overpass_lookup(hebrew_name):
    """
    Query Overpass API for OSM elements whose name:he tag exactly matches.
    Falls back to name tag if name:he yields nothing.
    Returns (lat, lng, match_info) or (None, None, error_msg).
    """
    last_err = ""
    for tag in ("name:he", "name"):
        query = (
            f'[out:json][timeout:30];'
            f'('
            f'  node["place"]["{tag}"="{hebrew_name}"]({OVERPASS_BBOX});'
            f'  way["place"]["{tag}"="{hebrew_name}"]({OVERPASS_BBOX});'
            f'  relation["place"]["{tag}"="{hebrew_name}"]({OVERPASS_BBOX});'
            f');out center tags;'
        )
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req  = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=data,
            headers={"User-Agent": USER_AGENT},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    result   = json.loads(resp.read())
                    elements = result.get("elements", [])
                    if elements:
                        el  = elements[0]
                        lat, lng = _element_coords(el)
                        tags = el.get("tags", {})
                        display = tags.get("name:he", tags.get("name", hebrew_name))
                        return lat, lng, f"{display} [Overpass {tag}]"
                    break  # empty — no point retrying
            except urllib.error.HTTPError as e:
                last_err = str(e)
                if e.code in (429, 504) and attempt < 3:
                    time.sleep(10 * (2 ** attempt))
                    continue
                break
            except Exception as e:
                last_err = str(e)
                break
        time.sleep(5)

    return None, None, f"No Overpass match{(': ' + last_err) if last_err else ''}"


def main():
    apply_mode  = "--apply"       in sys.argv
    resume_mode = "--resume"      in sys.argv
    jewish_only = "--jewish-only" in sys.argv

    log_fh = open(LOG_FILE, "w", encoding="utf-8")
    sys.stdout = TeeWriter(log_fh, sys.__stdout__)

    with open(LOCALITIES_FILE, encoding="utf-8") as f:
        localities = json.load(f)

    mode_label = (
        " (APPLY MODE — writing israel_localities.json)" if apply_mode
        else " (dry run — use --apply to write)"
    )
    resume_label = " [--resume: skipping already-fetched]" if resume_mode else ""
    jewish_label = " [--jewish-only: skipping Arab localities]" if jewish_only else ""
    total = len(localities)
    print(f"Processing {total} localities...{mode_label}{resume_label}{jewish_label}\n")
    print(f"{'Hebrew Name':<30} {'Method':<10} {'Coordinates':>26}  Status")
    print("-" * 90)

    matched   = 0
    unmatched = 0
    skipped   = 0
    arab_skip = 0

    for entry in localities:
        hebrew = entry.get("Hebrew Name", "")

        # --jewish-only: skip obvious Arab localities
        if jewish_only and is_arab(entry):
            arab_skip += 1
            print(f"  {hebrew:<28} {'—':<10} {'':>26}  SKIPPED (Arab)")
            continue

        # --resume: skip entries that already have a coord field
        if resume_mode and "coord" in entry:
            skipped += 1
            continue

        if not hebrew:
            entry["coord"] = "UNMATCHED"
            unmatched += 1
            print(f"  {'(empty)':<28} {'—':<10} {'':>26}  UNMATCHED (no Hebrew name)")
            continue

        # ── Method 1: Nominatim ───────────────────────────────────────────────
        time.sleep(1.1)  # Nominatim: max 1 req/sec
        lat, lng, info = nominatim_lookup(hebrew)
        method = "Nominatim"

        # ── Method 2: Overpass fallback ───────────────────────────────────────
        if lat is None:
            lat, lng, info = overpass_lookup(hebrew)
            method = "Overpass"

        coord_str = f"({lat:.4f}, {lng:.4f})" if lat is not None else ""

        if lat is not None:
            entry["coord"] = {"lat": round(lat, 6), "lng": round(lng, 6)}
            matched += 1
            print(f"  {hebrew:<28} {method:<10} {coord_str:>26}  OK  {info[:60]}")
        else:
            entry["coord"] = "UNMATCHED"
            unmatched += 1
            print(f"  {hebrew:<28} {method:<10} {'':>26}  UNMATCHED  {info}")

    print("\n" + "=" * 90)
    print(f"\nSUMMARY: {matched} matched, {unmatched} unmatched, {skipped} skipped (--resume), {arab_skip} skipped (--jewish-only)")
    print(f"  Total entries: {total}")

    if apply_mode:
        with open(LOCALITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(localities, f, ensure_ascii=False, indent=4)
        print(f"\nWrote updated {LOCALITIES_FILE}")
    else:
        print("\nRun with --apply to save coordinates to israel_localities.json.")

    unmatched_entries = [e["Hebrew Name"] for e in localities if e.get("coord") == "UNMATCHED"]
    if unmatched_entries:
        print(f"\nUNMATCHED ({len(unmatched_entries)}):")
        for name in unmatched_entries:
            print(f"  {name}")

    log_fh.close()
    sys.stdout = sys.__stdout__
    print(f"\nLog written to: {LOG_FILE}")


if __name__ == "__main__":
    main()
