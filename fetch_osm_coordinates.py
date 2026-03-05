#!/usr/bin/env python3
"""
Fetch OSM coordinates for every locality in israel_localities.json using
the Hebrew name (name:he OSM tag / Nominatim Hebrew query).

HOW IT WORKS
------------
For each locality the script tries two methods in order:

  1. Nominatim free-text search with the Hebrew name, bounded to the
     Israel + West Bank bounding box.

  2. Overpass API fallback — queries OSM directly for nodes/ways/relations
     whose name:he tag exactly matches the Hebrew name, then falls back
     to the name tag.

Matched entries get:  "coord": {"lat": <float>, "lng": <float>}
Unmatched entries get: "coord": "UNMATCHED"   <- easy to grep/filter

USAGE
-----
    python3 fetch_osm_coordinates.py                      # dry run
    python3 fetch_osm_coordinates.py --apply              # write updated israel_localities.json
    python3 fetch_osm_coordinates.py --resume             # skip entries that already have coord
    python3 fetch_osm_coordinates.py --jewish-only        # skip obvious Arab localities
    python3 fetch_osm_coordinates.py --apply --resume --jewish-only   # combine flags

Recommended workflow for large runs:
    python3 fetch_osm_coordinates.py --apply --resume --jewish-only
    # Re-run as many times as needed; --resume skips already-fetched entries
    # so transient API failures are automatically retried on the next run.

REQUIREMENTS
------------
Python 3.7+, standard library only.
Nominatim rate limit: 1 req/sec (enforced automatically).
"""

import sys
import os
import time
import json
import urllib.request
import urllib.parse
import urllib.error

# ── Israel + West Bank bounding box ─────────────────────────────────────────
# Nominatim viewbox: left(lon_min), top(lat_max), right(lon_max), bottom(lat_min)
NOMINATIM_VIEWBOX = "34.0,33.5,36.0,29.0"
# Overpass bbox: S,W,N,E
OVERPASS_BBOX = "29.0,34.0,33.5,36.0"
COUNTRY_CODES = "il,ps"

LOCALITIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "israel_localities.json")
LOG_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_osm_coordinates.log")
USER_AGENT      = "GillyGeoGuesser-coord-fetcher/1.0"

# ── Arab-locality heuristics for --jewish-only ───────────────────────────────
# No false positives on Jewish towns, but ~200 Arab towns with Hebrew-
# transliterated names (Ar'Ara, Arrabe, Baqa, etc.) will not be caught.
ARAB_HEB_MARKERS  = ["(שבט)"]                              # Bedouin tribe suffix
ARAB_HEB_PREFIXES = ["אבו "]                               # Abu...
ARAB_ENG_PREFIXES = ["Abu ", "Al ", "Al-", "Kafr ", "Bir ", "Umm ", "Um "]

_last_nominatim_call = 0.0   # tracks last call time to enforce Nominatim rate limit


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
    Single-attempt Nominatim search bounded to Israel + West Bank.
    Returns (lat, lng, display_name) or (None, None, error_msg).
    Rate-limited to 1 req/sec; sleeps only the remaining gap.
    """
    global _last_nominatim_call
    gap = time.time() - _last_nominatim_call
    if gap < 1.1:
        time.sleep(1.1 - gap)

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
    _last_nominatim_call = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read())
            if results:
                place_results = [r for r in results if r.get("class") == "place"]
                best = place_results[0] if place_results else results[0]
                return float(best["lat"]), float(best["lon"]), best.get("display_name", "")
    except Exception as e:
        return None, None, f"Nominatim error: {e}"
    return None, None, "No Nominatim result"


def _element_coords(el):
    if "center" in el:
        return float(el["center"]["lat"]), float(el["center"]["lon"])
    return float(el["lat"]), float(el["lon"])


def overpass_lookup(hebrew_name):
    """
    Single-attempt Overpass search for elements with name:he == hebrew_name,
    then falls back to name tag.  No sleeps — fast fail for non-existent places.
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
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                result   = json.loads(resp.read())
                elements = result.get("elements", [])
                if elements:
                    el   = elements[0]
                    lat, lng = _element_coords(el)
                    tags = el.get("tags", {})
                    display = tags.get("name:he", tags.get("name", hebrew_name))
                    return lat, lng, f"{display} [Overpass {tag}]"
        except Exception as e:
            last_err = str(e)

    return None, None, f"No Overpass match{(': ' + last_err) if last_err else ''}"


def main():
    apply_mode   = "--apply"       in sys.argv
    resume_mode  = "--resume"      in sys.argv
    jewish_only  = "--jewish-only" in sys.argv

    log_fh = open(LOG_FILE, "w", encoding="utf-8")
    sys.stdout = TeeWriter(log_fh, sys.__stdout__)

    with open(LOCALITIES_FILE, encoding="utf-8") as f:
        localities = json.load(f)

    flags = []
    if apply_mode:   flags.append("--apply")
    if resume_mode:  flags.append("--resume")
    if jewish_only:  flags.append("--jewish-only")
    flag_str = " ".join(flags) if flags else "dry run"

    total = len(localities)
    print(f"Processing {total} localities... [{flag_str}]\n")
    print(f"{'Hebrew Name':<30} {'Method':<10} {'Coordinates':>26}  Status")
    print("-" * 90)

    matched   = 0
    unmatched = 0
    skipped   = 0
    arab_skip = 0

    output_localities = []

    for entry in localities:
        hebrew = entry.get("Hebrew Name", "")

        # --jewish-only: drop obvious Arab entries entirely
        if jewish_only and is_arab(entry):
            arab_skip += 1
            print(f"  {hebrew:<28} {'—':<10} {'':>26}  SKIPPED (Arab)")
            continue

        output_localities.append(entry)

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
    processed = total - arab_skip - skipped
    print(f"\nSUMMARY")
    print(f"  Total entries    : {total}")
    print(f"  Arab skipped     : {arab_skip}  (--jewish-only)")
    print(f"  Already fetched  : {skipped}  (--resume)")
    print(f"  Processed        : {processed}")
    print(f"  Matched          : {matched}")
    print(f"  Unmatched        : {unmatched}")
    if processed:
        print(f"  Match rate       : {matched / processed * 100:.1f}%")

    if apply_mode:
        with open(LOCALITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(output_localities, f, ensure_ascii=False, indent=4)
        print(f"\nWrote {len(output_localities)} entries to {LOCALITIES_FILE}")
    else:
        print("\nRun with --apply to save coordinates to israel_localities.json.")

    unmatched_entries = [e["Hebrew Name"] for e in output_localities if e.get("coord") == "UNMATCHED"]
    if unmatched_entries:
        print(f"\nUNMATCHED ({len(unmatched_entries)}):")
        for name in unmatched_entries:
            print(f"  {name}")

    log_fh.close()
    sys.stdout = sys.__stdout__
    print(f"\nLog written to: {LOG_FILE}")


if __name__ == "__main__":
    main()
