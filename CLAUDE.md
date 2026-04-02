# Gilly's Israel Quiz — Project Guide

## What This Is
A browser-based PWA geo-guessing game where players click on a map of Israel to identify cities and towns. Has a standard mode and a "senior" mode (simplified).

## Structure
- `index.html` — Main game (all HTML + JS in one file, ~450KB)
- `towns.js` — Town data for the main game
- `senior/` — Simplified version for older users
  - `senior/towns.js` — Town data for senior mode
- `sw.js` — Service worker for PWA offline support
- `manifest.json` — PWA manifest
- `firestore.rules` — Firestore security rules (multiplayer)
- `israel_localities_with_coords.json` — Source data with coordinates
- `israel_localities.json` — Source locality data

## Data Pipeline (Python scripts)
- `fetch_osm_coordinates.py` — Fetches coordinates from OpenStreetMap
- `validate_coords.py` — Validates coordinate data
- `apply_verified_coords.py` — Applies verified coordinates to towns.js
- `sync_towns_coords.py` — Syncs coordinate data
- `append_localities.py` — Appends new localities to data

## Key Facts
- No build system — plain HTML/JS, edit files directly
- No test suite
- Multiplayer uses Firebase/Firestore
- The main game logic lives entirely in `index.html`
- `towns.js` and `senior/towns.js` are large JS files (not modules)
- Development branch convention: `claude/<feature-name>-<id>`
- Push to `origin` and open PRs against `main`
