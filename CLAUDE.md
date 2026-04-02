# Gilly's Israel Quiz — Project Guide

## What This Is
A browser-based PWA geo-guessing game where players click on a map of Israel to identify cities and towns. Hosted at gilly.co.il. Has standard, senior (simplified), daily challenge, learning, challenge (share a single town), and multiplayer modes.

## Project Structure
```
index.html          — Main game: ALL HTML, CSS, and JS in one file (~10,800 lines)
towns.js            — Town data array (TOWNS), ~1,300 lines
senior/             — Simplified version for older users
  index.html        — Senior game (~7,400 lines, same single-file pattern)
  towns.js          — Senior town data (~1,300 lines)
sw.js               — Minimal service worker (PWA installability only)
manifest.json       — PWA manifest
firestore.rules     — Firestore security rules (multiplayer, scores, daily)
accessibility.html  — Accessibility statement page
coordinate-picker.html — Dev tool for picking coordinates on a map
```

## Town Data Format (towns.js)
Each entry in the `TOWNS` array:
```js
{ name:"Tel Aviv", lat:32.0853, lng:34.7818, region:"Center", tier:1,
  desc:"...", nameHe:"תל אביב", descHe:"...",
  fact:"...", factHe:"...",
  arabVillage: true  // optional flag for Arab villages
}
```
- **Tiers**: 1 = major cities (easy), 2 = medium towns, 3 = small towns, 4 = villages/junctions
- **Regions**: "Center", "North", "South", "Jerusalem"
- Both `towns.js` and `senior/towns.js` define a global `TOWNS` array (not a module)

## Key Architecture Decisions

### index.html Organization (~line numbers)
- **Lines 1–100**: Head, meta tags, Firebase SDK imports, Firebase init (exposed to `window._fb*`)
- **Lines 100–4660**: All CSS + all HTML (menus, modals, HUD, map container, overlays)
- **Line 4663**: `<script src="towns.js">` — loads TOWNS array
- **Lines 4665–5070**: Constants, scoring math, difficulty config, i18n strings (STRINGS object, `t()` helper)
- **Lines 5070–5400**: Language/map-layer setup, border drawing, street layer management
- **Lines 5400–6100**: UI utilities: focus traps, mobile tools, fact modals, daily challenge seeded RNG
- **Lines 6100–7200**: Core game loop: `shuffle`, `haversineKm`, `loadTown`, `onMapClick`, `_processMapClick`, `showResults`, polygon-based perfect scoring
- **Lines 7200–7800**: Learning mode: `startLearning`, `handleLearningClick`, `showLearningResults`, level-up system
- **Lines 7800–9300**: Auth (Firebase Google + email), score saving, leaderboard, settings modal, share/QR
- **Lines 9300–9600**: Challenge mode (share a single-town quiz link)
- **Lines 9600–10500**: Multiplayer (Firebase Realtime via Firestore: room creation, lobby, round sync, leaderboard)
- **Lines 10500–10800**: PWA install prompt logic

### External Dependencies (CDN, no npm)
- Leaflet 1.9.4 (map rendering)
- Firebase 10.12.0 (auth, Firestore, analytics, App Check with reCAPTCHA v3)
- QRCode.js 1.0.0 (share QR codes)
- Google Fonts: Alef, Playfair Display, Source Serif 4

### Bilingual (English + Hebrew)
- All UI strings in `STRINGS` object with `en` and `he` keys
- `t(key)` returns the current language's string
- Town data has both `name`/`desc`/`fact` (English) and `nameHe`/`descHe`/`factHe` (Hebrew)
- Language toggled via `toggleLang()`, stored in `localStorage`

## Data Pipeline (Python scripts)
- `fetch_osm_coordinates.py` — Fetches coordinates from OpenStreetMap Nominatim
- `validate_coords.py` — Validates coordinate data against known locations
- `apply_verified_coords.py` — Applies verified coordinates back into towns.js
- `sync_towns_coords.py` — Syncs coordinates between towns.js and JSON data files
- `append_localities.py` — Adds new localities from israel_localities.json

## Important Conventions
- **No build system** — plain HTML/JS/CSS, edit files directly, no transpilation
- **No test suite** — test changes by opening in a browser
- **Single-file architecture** — resist splitting index.html; the project intentionally keeps everything in one file
- **Service worker is minimal** — only exists for PWA installability, no caching strategy
- **Firebase config is in index.html** — these are client-side keys (public by design, secured by Firestore rules + App Check)
- **senior/ is a separate copy** — not shared code; changes to the main game are not automatically reflected in senior mode
