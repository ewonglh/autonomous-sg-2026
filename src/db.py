import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    host_key_hash TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    active_question_id INTEGER
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    position INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('multiple_choice', 'word_cloud')),
    text TEXT NOT NULL,
    is_open INTEGER NOT NULL DEFAULT 1,
    results_visible INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    position INTEGER NOT NULL,
    label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    participant_id TEXT NOT NULL,
    option_id INTEGER REFERENCES options(id),
    text TEXT,
    created_at TEXT NOT NULL
);
-- One vote per participant for multiple choice only (word cloud rows have no option_id).
CREATE UNIQUE INDEX IF NOT EXISTS one_vote_per_participant
    ON responses (question_id, participant_id) WHERE option_id IS NOT NULL;
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", "crowdpulse.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
