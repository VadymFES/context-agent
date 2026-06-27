# Context Agent

A Windows background agent that watches your active window, OCR-captures the screen on every window change, matches captured text against your defined goals, and uses Claude AI to produce structured summaries of your work sessions — including main ideas, important notes, recommendations, and resource links. Everything is stored locally in a SQLite database with full-text search.

---

## How it works

1. You define **goals** — a name and a set of keywords (e.g. "job search" with keywords `linkedin jobs resume`)
2. The watcher polls the foreground window every 0.5 seconds
3. When the window title changes, it OCR-captures the active window area
4. If the OCR text contains any of your keywords, the capture is added to the current session
5. When you stop the watcher (Ctrl+C), all captures are sent to Claude in one call
6. Claude filters out off-topic content, summarizes only what is relevant to your goal, and extracts links
7. The summary is saved to the local database and printed to the console
8. After each session, Claude updates a persistent user context file (`data/user_context.md`) so future summaries improve over time

---

## Requirements

- **Windows only** (uses `win32gui` / `win32process`)
- **Python 3.11+**
- **Tesseract OCR** with `eng` and `ukr` language packs installed and on PATH
  - Download: https://github.com/UB-Mannheim/tesseract/wiki
- **Anthropic API key** for AI summarization

---

## Installation

**1. Clone the repo and create a virtual environment**

```bash
git clone <repo-url>
cd context-agent
python -m venv venv
venv\Scripts\activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up your API key**

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The `.env` file is gitignored and never committed.

---

## Usage

### Add a goal

```bash
python main.py add-goal "<goal name>" <keyword1> <keyword2> ...
```

The goal name is a label shown in logs and search results. Keywords are space-separated — any one of them appearing in the OCR text triggers a capture.

**Examples:**

```bash
python main.py add-goal "job search" linkedin jobs resume vacancy junior
python main.py add-goal "1c migration" 1c dilovod migration
python main.py add-goal "python learning" python tutorial docs documentation
```

You can have multiple active goals at once. A capture is saved if it matches any of them.

### Start watching

```bash
python main.py
```

Or add a goal and immediately start watching:

```bash
python main.py add-goal "job search" linkedin jobs resume --watch
```

While watching, the console prints a `[+]` line for every capture. Switch between windows freely — captures accumulate silently. Press **Ctrl+C** to stop.

On stop, the agent:
- Sends all accumulated captures to Claude
- Filters out anything not related to your goal topic
- Prints a structured summary to the console
- Saves the session to the database
- Updates your user context file for better future summaries

If a session is very long (100K+ characters of OCR text), an intermediate summary is automatically triggered mid-session without stopping the watcher. At the end, all partial summaries are merged into one final conclusion.

### Search past sessions

```bash
python main.py search <query>
```

**Examples:**

```bash
python main.py search junior
python main.py search linkedin
python main.py search python
```

Search uses SQLite FTS5 with a trigram index — fast full-text search over all captured OCR text and summaries. Queries shorter than 3 characters fall back to a LIKE scan automatically.

Each result shows:
- Timestamp, app, and window title
- AI summary (what you were doing, main ideas, notes, recommendations)
- Links found in the session
- A snippet of the raw OCR text

---

## Console output explained

```
[+] chrome.exe — Junior Data Analyst Jobs | LinkedIn → goals [1]
[+] chrome.exe — Data Analyst Roadmap - Google Chrome → goals [1]

[session] Summarizing final 2 capture(s)...
[session] The user was researching junior data analyst job opportunities on LinkedIn
          and reviewing a data analyst learning roadmap to understand required skills.
[session] Ideas: SQL and Python are the most requested skills; entry-level roles expect
          1-2 years experience or a portfolio; Kyiv market has ~40 open positions
[session] Notes: Most listings require knowledge of Power BI or Tableau; some require English B2+
[session] Tips: Build 2-3 portfolio projects on Kaggle before applying; target companies
               with trainee programs; tailor your CV to each listing
[session] Links: https://www.linkedin.com/jobs/data-analyst, https://roadmap.sh/data-analyst
[context] User context updated.
Stopped.
```

---

## File structure

```
context-agent/
├── main.py          — CLI entry point and session management
├── watcher.py       — Foreground window polling (win32gui)
├── capture.py       — Screenshot + Tesseract OCR
├── normalize.py     — Text normalization (lowercase, strip punctuation)
├── goals.py         — Keyword matching against OCR text
├── storage.py       — SQLite database (goals, moments, FTS5 index)
├── summarize.py     — Claude API integration (summarize, merge, context update)
├── requirements.txt
├── .env             — Your API key (gitignored)
└── data/
    ├── data.db          — SQLite database (gitignored)
    └── user_context.md  — Persistent user context updated after each session (gitignored)
```

---

## Database

The database is created automatically at `data/data.db` on first run.

**`goals`** — your defined goals
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Goal label |
| keywords | TEXT | JSON array of keyword strings |
| active | INTEGER | 1 = active, 0 = disabled |
| created_at | INTEGER | Unix timestamp |

**`moments`** — captured sessions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| timestamp | INTEGER | Unix timestamp of capture |
| window_title | TEXT | Window title(s) seen during the session |
| app_name | TEXT | Application executable name |
| ocr_text | TEXT | Normalized OCR text (used for FTS search) |
| matched_goals | TEXT | JSON array of matched goal IDs |
| summary | TEXT | AI-generated summary (plain text, multi-line) |
| links | TEXT | JSON array of URLs extracted by AI |

**`moments_fts`** — FTS5 virtual table with trigram tokenizer, synced automatically via an AFTER INSERT trigger on `moments`.

---

## User context memory

After each session, Claude rewrites `data/user_context.md` with a concise profile of the user — inferred role, current focus areas, observed patterns, and key facts — built up from all past sessions. This file is loaded at the start of every summarization call, so the quality of summaries improves progressively as the agent learns your work context.

The file is plain text, under 500 words, and gitignored. You can edit or delete it at any time.

---

## Notes

- Only the **active window area** is captured (not the full screen), which eliminates bleed from sidebars, taskbars, and background windows
- Sessions are stored as **one record per watcher run** — individual window captures are not saved separately
- The agent never uploads screenshots — only OCR text is sent to the Claude API
- All data stays local except the OCR text sent for summarization
