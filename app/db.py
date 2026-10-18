"""
db.py - the SQLite database: table definitions and small helper functions.

Tables and why each exists:
  brand_profiles    - a brand's sample posts and the voice profile learned from them
  content_pieces    - one row per post: the brief, the strategy choices, final text, image, schedule
  drafts            - every version of a post with the editor's score (proves the editor loop works)
  engagement        - likes/comments/shares per post (real, typed in, or simulated)
  playbook_versions - what the system has learned, one new row each time it learns something
  decisions         - the audit trail: which agent decided what, and why
  llm_calls         - a log of every Mesh call (agent, model, tokens, time)
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "creatoros.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS brand_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    sample_posts  TEXT NOT NULL,          -- JSON list of the user's past posts
    profile       TEXT,                   -- JSON voice profile made by the Voice Analyst
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_pieces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    brief             TEXT NOT NULL,
    platform          TEXT NOT NULL,      -- linkedin / x / instagram
    brand_profile_id  INTEGER REFERENCES brand_profiles(id),
    playbook_version  INTEGER,            -- which learned playbook was used (NULL = none)
    hook_type         TEXT,               -- question / stat / story / contrarian / bold_claim
    length_bucket     TEXT,               -- short / medium / long
    cta_style         TEXT,               -- question / link / none / follow
    emoji_level       TEXT,               -- none / light / heavy
    time_slot         TEXT,               -- morning / midday / evening
    strategy          TEXT,               -- full JSON from the Strategist
    final_text        TEXT,
    image_prompt      TEXT,
    image_path        TEXT,
    status            TEXT NOT NULL DEFAULT 'draft',  -- draft / scheduled / published
    scheduled_for     TEXT,
    published_at      TEXT,
    run_label         TEXT,               -- used by evals to group runs (e.g. 'learning', 'control')
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id       INTEGER NOT NULL REFERENCES content_pieces(id),
    version          INTEGER NOT NULL,
    text             TEXT NOT NULL,
    editor_score     REAL,
    editor_feedback  TEXT,                -- JSON from the Editor
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engagement (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id   INTEGER NOT NULL REFERENCES content_pieces(id),
    impressions  INTEGER,
    likes        INTEGER,
    comments     INTEGER,
    shares       INTEGER,
    score        REAL,                    -- one combined engagement number
    source       TEXT NOT NULL,           -- simulated / manual / platform
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playbook_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     INTEGER NOT NULL,
    brand_profile_id INTEGER REFERENCES brand_profiles(id),
    rules       TEXT NOT NULL,            -- JSON list of learned rules
    evidence    TEXT,                     -- JSON stats that justify the rules
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id  INTEGER REFERENCES content_pieces(id),
    agent       TEXT NOT NULL,
    decision    TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    agent              TEXT,
    model              TEXT,
    kind               TEXT,              -- chat / image
    content_id         INTEGER,
    prompt_tokens      INTEGER,
    completion_tokens  INTEGER,
    seconds            REAL,
    created_at         TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # lets us read columns by name: row["text"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert(table: str, **values) -> int:
    """Insert one row and return its new id. Dicts/lists are stored as JSON."""
    values.setdefault("created_at", now())
    values = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in values.items()}
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with get_conn() as conn:
        cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))
        return cur.lastrowid


def update(table: str, row_id: int, **values) -> None:
    values = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in values.items()}
    sets = ", ".join(f"{k} = ?" for k in values)
    with get_conn() as conn:
        conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])


def fetch_all(sql: str, params=()) -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fetch_one(sql: str, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def log_decision(content_id, agent: str, decision: str, reason: str = None) -> int:
    return insert("decisions", content_id=content_id, agent=agent, decision=decision, reason=reason)


def log_llm_call(**values) -> None:
    try:
        insert("llm_calls", **values)
    except Exception:
        pass  # logging must never break a real call


init_db()
