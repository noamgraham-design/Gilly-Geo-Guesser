#!/usr/bin/env python3
"""
Append to towns.js all localities from israel_localities_with_coords.json
that are not already present in towns.js, using placeholder desc/fact text.

USAGE
-----
    python3 append_localities.py           # dry run — print stats + first 20 new entries
    python3 append_localities.py --apply   # write updated towns.js
"""

import sys
import re
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
TOWNS_FILE      = os.path.join(BASE, "towns.js")
LOCALITIES_FILE = os.path.join(BASE, "israel_localities_with_coords.json")

apply_mode = "--apply" in sys.argv


# ── 1. Parse existing towns.js entries ───────────────────────────────────────
with open(TOWNS_FILE, encoding="utf-8") as f:
    towns_text = f.read()

ENTRY_RE = re.compile(
    r'name:"([^"]+)"[^}]*?nameHe:"([^"]+)"'
)
existing_eng = set()
existing_heb = set()
for name, nameHe in ENTRY_RE.findall(towns_text):
    existing_eng.add(name)
    existing_heb.add(nameHe)

print(f"Existing towns.js entries: {len(existing_eng)}")


# ── 2. Filter localities to candidates ───────────────────────────────────────
with open(LOCALITIES_FILE, encoding="utf-8") as f:
    localities = json.load(f)

candidates = []
skipped_no_coord   = 0
skipped_no_eng     = 0
skipped_duplicate  = 0

for entry in localities:
    if "coord" not in entry or not isinstance(entry["coord"], dict):
        skipped_no_coord += 1
        continue
    eng = entry.get("English Name", "").strip()
    heb = entry.get("Hebrew Name", "").strip()
    if not eng:
        skipped_no_eng += 1
        continue
    if eng in existing_eng or heb in existing_heb:
        skipped_duplicate += 1
        continue
    candidates.append(entry)

print(f"Localities total          : {len(localities)}")
print(f"  Skipped (no coord)      : {skipped_no_coord}")
print(f"  Skipped (no English name): {skipped_no_eng}")
print(f"  Skipped (already in JS) : {skipped_duplicate}")
print(f"  New entries to append   : {len(candidates)}")


# ── 3. Format new entries ─────────────────────────────────────────────────────
def escape_js_str(s):
    """Escape backslash and double-quote for a JS double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')

new_lines = []
for entry in candidates:
    eng  = escape_js_str(entry["English Name"].strip())
    heb  = escape_js_str(entry["Hebrew Name"].strip())
    lat  = round(entry["coord"]["lat"], 4)
    lng  = round(entry["coord"]["lng"], 4)
    tier = int(entry.get("Tier", 3))
    region = entry.get("Location", "Center").strip()

    line = (
        f'  {{ name:"{eng}", lat:{lat}, lng:{lng}, region:"{region}", tier:{tier}, '
        f'desc:"Israeli locality", nameHe:"{heb}", descHe:"יישוב ישראלי", '
        f'fact:"", factHe:"", arabVillage:false }},'
    )
    new_lines.append(line)

print(f"\nFirst 20 new entries (preview):")
for line in new_lines[:20]:
    print(" ", line[:120])


# ── 4. Insert before closing `];` ────────────────────────────────────────────
if apply_mode:
    # Find the last `];` in the file (end of TOWNS array)
    insert_pos = towns_text.rfind("];")
    if insert_pos == -1:
        sys.exit("ERROR: Could not find closing ]; in towns.js")

    block = "\n  // ── Imported from israel_localities_with_coords.json ──────────────────────\n"
    block += "\n".join(new_lines) + "\n"

    updated_text = towns_text[:insert_pos] + block + towns_text[insert_pos:]

    with open(TOWNS_FILE, "w", encoding="utf-8") as f:
        f.write(updated_text)
    print(f"\nWrote {len(candidates)} new entries to {TOWNS_FILE}")
else:
    print(f"\nDry run — run with --apply to write towns.js")
