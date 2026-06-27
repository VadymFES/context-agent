# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.
Update the "Session log" section at the end of every working session before closing.

## What this project does

A Windows-only background agent that watches the active window, OCR-captures
the screen on each window change, matches the text against user-defined keyword
goals, and stores matching "moments" in a local SQLite database with full-text
search.

## Running the project

Requires Python (venv in `venv/`) and Tesseract OCR installed on PATH
with `eng` and `ukr` language data.
Download: https://github.com/UB-Mannheim/tesseract/wiki

```bash
# Activate venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the watcher
python main.py

# Add a goal with keywords
python main.py add-goal "1c migration" 1c dilovod migration

# Search captured moments
python main.py search migration
```

No tests, no linter configured yet.

## Architecture

All logic lives in six flat modules — no packages.

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI entry point; dispatches `add-goal`, `search`, or starts the watcher loop |
| `watcher.py` | Polls `win32gui` every 0.5s; fires `on_change(title, app)` when foreground window title changes |
| `capture.py` | Grabs primary monitor via `mss`, runs `pytesseract` (eng+ukr), returns normalized text |
| `normalize.py` | Lowercases, strips punctuation, collapses whitespace — shared by `capture.py` and `goals.py` |
| `goals.py` | Checks whether any normalized keyword appears in OCR text; returns matched goal IDs |
| `storage.py` | SQLite at `data/data.db` (project-local, git-ignored); FTS5 trigram index on `moments` |

**Data flow:** `watcher` → `capture` → `goals.match_goals` → `storage.save_moment`

## Database

Created automatically at `data/data.db` (relative to the project root) on first run.

- `goals` — name, JSON keyword array, active flag
- `moments` — timestamp, window title, app name, OCR text, matched goal IDs
- `moments_fts` — FTS5 virtual table (trigram tokenizer), synced via AFTER INSERT trigger

## Known issues to fix before v1

_(all resolved)_

## Platform

Hard dependency on Windows APIs (`win32gui`, `win32process` from `pywin32`).
Will not run on macOS or Linux.
Linux X11 support planned for v2.

## Session log

Update this section manually at the end of every session.
Format: date — what was done — what's next.

---

**2026-06-27**
- Fixed `capture.py`: now grabs active window rect via `win32gui.GetWindowRect()` instead of full monitor — eliminates sidebar/tab bleed and false positives
- Fixed `storage.py`: queries < 3 chars fall back to `LIKE` on `moments` directly, bypassing FTS5 trigram minimum — fixes `1c` and similar short queries
- Added AI summarization via Claude (`claude-opus-4-8`): new `summarize.py`; `capture_screen` now returns `(normalized, raw)` tuple; session-based accumulation in `main.py` — window captures aggregate until the user switches to a non-matching window or Ctrl+C, then one Claude call summarizes the full session; `moments` table gains `summary` and `links` columns with automatic migration; `search` output shows summary and links
- Requires `ANTHROPIC_API_KEY` in `.env`; run `pip install anthropic python-dotenv`
- Next: nothing blocking v1

**2026-06-18**
- PoC complete: all six modules written and tested on real workflow
- Pipeline confirmed working: window hook → OCR → keyword match → SQLite save → search
- Tested with goal "1c migration", keywords: 1c dilovod migration
- Search confirmed working for queries 3+ chars (trigram FTS5 minimum)
- Known issue confirmed: OCR reads full monitor, not just active window
- Next: fix `capture.py` to crop active window bounds before v1