import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path.home() / ".context-agent" / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    keywords   TEXT    NOT NULL,
    active     INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS moments (
    id              INTEGER PRIMARY KEY,
    timestamp       INTEGER NOT NULL,
    window_title    TEXT,
    app_name        TEXT,
    ocr_text        TEXT,
    matched_goals   TEXT,
    screenshot_path TEXT,
    source_type     TEXT DEFAULT 'screen'
);

CREATE VIRTUAL TABLE IF NOT EXISTS moments_fts USING fts5(
    ocr_text,
    window_title,
    content='moments',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS moments_ai
AFTER INSERT ON moments BEGIN
    INSERT INTO moments_fts(rowid, ocr_text, window_title)
    VALUES (new.id, new.ocr_text, new.window_title);
END;
"""


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def add_goal(conn, name: str, keywords: list[str]) -> int:
    cur = conn.execute(
        "INSERT INTO goals (name, keywords, created_at) VALUES (?, ?, ?)",
        (name, json.dumps(keywords), int(time.time()))
    )
    conn.commit()
    return cur.lastrowid


def get_active_goals(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, keywords FROM goals WHERE active = 1"
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "keywords": json.loads(r[2])}
        for r in rows
    ]


def save_moment(conn, window_title: str, app_name: str,
                ocr_text: str, matched_goals: list[int]):
    conn.execute(
        """INSERT INTO moments
           (timestamp, window_title, app_name, ocr_text, matched_goals)
           VALUES (?, ?, ?, ?, ?)""",
        (int(time.time()), window_title, app_name,
         ocr_text, json.dumps(matched_goals))
    )
    conn.commit()


def search(conn, query: str) -> list[dict]:
    rows = conn.execute(
        """SELECT m.timestamp, m.window_title, m.app_name,
                  m.ocr_text, m.matched_goals
           FROM moments_fts f
           JOIN moments m ON f.rowid = m.id
           WHERE moments_fts MATCH ?
           ORDER BY rank
           LIMIT 20""",
        (query,)
    ).fetchall()
    return [
        {
            "ts":    r[0],
            "title": r[1],
            "app":   r[2],
            "text":  r[3][:200],
            "goals": json.loads(r[4])
        }
        for r in rows
    ]