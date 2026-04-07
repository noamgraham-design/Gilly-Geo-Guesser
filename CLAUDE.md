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

### Two town arrays in towns.js
| Array | Used in |
|-------|---------|
| `TOWNS` | Quiz, Daily Challenge, Learning mode, Multiplayer — all game modes |
| `CHALLENGE_ONLY_TOWNS` | WhatsApp Challenge mode only — not available in any other mode |

`ALL_TOWNS = [...TOWNS, ...CHALLENGE_ONLY_TOWNS]` is the combined list used only for challenge town search.
`CHALLENGE_ONLY_TOWNS` entries typically have empty `fact`/`factHe` fields. When adding a new town, put it in `TOWNS` unless it should be challenge-only.

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

## Deployment
The game is deployed from a separate repo: `git@github.com:gillyisraelquiz/Gilly-Israel-Quiz.git`

Use `deploy.sh` to open a PR there — it uploads `index.html`, `towns.js`, `sw.js`, and `manifest.json` via the GitHub API and opens a PR for review:
```bash
export DEPLOY_GITHUB_TOKEN=your_pat  # PAT for gillyisraelquiz (once, or add to ~/.bashrc)
./deploy.sh                          # auto-generates PR title from latest commit
./deploy.sh "Add daily challenge"    # custom PR title
```
The PAT needs **Contents** (read/write) and **Pull Requests** (read/write) permissions on the deployment repo.

## Important Conventions
- **No build system** — plain HTML/JS/CSS, edit files directly, no transpilation
- **No test suite** — test changes by opening in a browser
- **Single-file architecture** — resist splitting index.html; the project intentionally keeps everything in one file
- **Service worker is minimal** — only exists for PWA installability, no caching strategy
- **Firebase config is in index.html** — these are client-side keys (public by design, secured by Firestore rules + App Check)
- **Ignore senior/** — do NOT read, edit, or modify anything under `senior/` unless explicitly asked. It is a separate copy maintained independently

## UI Style Guide
Match the existing visual language. Do not introduce new colors, fonts, or patterns.

### Design Tokens (CSS variables in `:root`)
```css
--bg:      #f4f6f9      /* page background */
--surface: #ffffff      /* card/modal background */
--border:  rgba(0,0,0,0.10)
--green:   #1a7f37      /* success, easy mode */
--red:     #cf2316      /* error, hard mode */
--gold:    #9a6700      /* warning, medium mode */
--text:    #1a1e27      /* primary text */
--muted:   #57606a      /* secondary/caption text */
```
Always use `var(--name)` — never hard-code these color values.

### Typography
- **Body**: `'Alef', sans-serif` (set on `body`)
- **Headings / hero numbers**: `'Playfair Display', 'Alef', serif` — bold/900 weight
- **Buttons / inputs / UI text**: `'Source Serif 4', 'Alef', serif`
- Never introduce additional font families

### Buttons (`.btn` base class, ~line 1083)
```css
.btn          /* border-radius: 50px; font: Source Serif 4; padding: 7px 16px */
.btn-primary  /* gradient: #1a6fd4 → #7c3aed; white text; blue shadow */
.btn-hint     /* transparent + dashed border; gold on hover */
.btn-learn    /* transparent + solid #7c3aed border; purple text */
.btn-mp-orange/* gradient: #f59e0b → #d97706; white text */
```
Reuse these classes. Don't create ad-hoc button styles.

### Modals & Overlays
All modals follow this pattern:
```css
/* Overlay backdrop */
display: none; position: fixed; inset: 0; z-index: <see scale>;
background: rgba(0,0,0,0.45);       /* semi-transparent backdrop */
align-items: center; justify-content: center;

/* Card inside */
background: var(--surface); border-radius: 20px;  /* or 16px, 24px */
box-shadow: 0 24px 60px rgba(0,0,0,0.25);         /* or 0 12px 48px */
padding: 28px 24px;
```
- Show with `el.style.display = 'flex'`, hide with `el.style.display = 'none'`
- Always add focus trap via `trapFocus(modal)` / `releaseFocus(modal)`

### z-index Scale
```
100000  — splash screen
20000   — confirm-home overlay
10000+  — modal overlays (login: 10100, terms/privacy: 10200, results: 10000)
9500–9800 — secondary modals (scoreboard, settings, share, challenge)
8000–9000 — floating UI (confirm popup, HUD overlays)
2000    — topbar, HUD elements
```
New modals should slot into existing ranges — don't invent new z-index values arbitrarily.

### Spacing & Radius Conventions
- **Card radius**: 20px (primary modals), 16px (smaller panels), 24px (hero cards like results/level-up)
- **Button radius**: 50px (pill buttons), 10px (rectangular action buttons), 14px (menu items)
- **Input radius**: 10px
- **Gap/padding**: use multiples of 4px (4, 8, 12, 14, 16, 20, 24, 28)

## RTL / Hebrew UI Rules
The app body is always `dir="ltr"`. Hebrew RTL is applied per-element, not globally. Follow these rules when touching Hebrew UI:

1. **Inline `dir="rtl"`**: When generating HTML with Hebrew text, add `dir="rtl"` on the container element (e.g., `<div dir="rtl">...</div>`)
2. **CSS `direction: rtl`**: For styled components that are always Hebrew (e.g., Hebrew-specific modals), use `direction: rtl; unicode-bidi: isolate;` in CSS
3. **`[dir="rtl"]` selectors**: When a component needs different layout in Hebrew (flipped margins, text-align), use `[dir="rtl"] .my-class { ... }` CSS selectors — see PWA install card for examples (~line 3663)
4. **Dynamic dir in JS**: When building HTML strings conditionally, use the pattern: `${lang === 'he' ? 'dir="rtl"' : ''}`. **Every** `<span>`, `<div>`, or element containing Hebrew text in JS-generated HTML must get `dir="rtl"` (or use `unicode-bidi: isolate` in CSS) — otherwise Hebrew renders in wrong order when embedded in LTR containers. Also prefix standalone Hebrew string literals with RLM (`\u200F`) when they appear inside mixed-direction contexts
5. **STRINGS object**: All new UI text must have both `en` and `he` keys in the `STRINGS` object and be accessed via `t('key')`
6. **Town data**: Always provide both English (`name`, `desc`, `fact`) and Hebrew (`nameHe`, `descHe`, `factHe`) fields
7. **Never set `document.body.dir = 'rtl'`** — the app explicitly keeps body LTR and handles RTL at the component level
