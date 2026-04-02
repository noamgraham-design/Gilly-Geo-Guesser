# Gilly's Israel Quiz — Project Guide

## What This Is
A browser-based PWA geo-guessing game where players click on a map of Israel to identify cities and towns. Hosted at gilly.co.il. Has standard, senior (simplified), daily challenge, learning, challenge (share a single town), and multiplayer modes.

## Project Structure
```
index.html          — Main game: ALL HTML, CSS, and JS in one file (~10,800 lines)
towns.js            — Town data array (TOWNS), ~1,300 lines
senior/             — Simplified version for older users (DO NOT touch unless asked)
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
- `towns.js` defines a global `TOWNS` array (not a module, loaded via `<script>` tag)

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
- **Ignore senior/** — do NOT read, edit, or modify anything under `senior/` unless explicitly asked. It is a separate copy maintained independently

## RTL / Hebrew UI Rules
The app body is always `dir="ltr"`. Hebrew RTL is applied per-element, not globally. Follow these rules when touching Hebrew UI:

1. **Inline `dir="rtl"`**: When generating HTML with Hebrew text, add `dir="rtl"` on the container element (e.g., `<div dir="rtl">...</div>`)
2. **CSS `direction: rtl`**: For styled components that are always Hebrew (e.g., Hebrew-specific modals), use `direction: rtl; unicode-bidi: isolate;` in CSS
3. **`[dir="rtl"]` selectors**: When a component needs different layout in Hebrew (flipped margins, text-align), use `[dir="rtl"] .my-class { ... }` CSS selectors — see PWA install card for examples (~line 3663)
4. **Dynamic dir in JS**: When building HTML strings conditionally, use the pattern: `${lang === 'he' ? 'dir="rtl"' : ''}`
5. **STRINGS object**: All new UI text must have both `en` and `he` keys in the `STRINGS` object and be accessed via `t('key')`
6. **Town data**: Always provide both English (`name`, `desc`, `fact`) and Hebrew (`nameHe`, `descHe`, `factHe`) fields
7. **Never set `document.body.dir = 'rtl'`** — the app explicitly keeps body LTR and handles RTL at the component level
