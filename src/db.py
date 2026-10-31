import os
import sqlite3
from datetime import datetime, timezone

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
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_session(code: str, host_key_hash: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    conn = connect()
    try:
        try:
            conn.execute(
                """INSERT INTO sessions
                   (code, host_key_hash, created_at, last_active_at)
                   VALUES (?, ?, ?, ?)""",
                (code, host_key_hash, now, now),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE code = ?", (code,)
            ).fetchone()
            if exists:
                return False
            raise
    finally:
        conn.close()


def get_host_key_hash(code: str) -> str | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT host_key_hash FROM sessions WHERE code = ?", (code,)
        ).fetchone()
        return row["host_key_hash"] if row else None
    finally:
        conn.close()


def create_question(
    code: str, question_type: str, text: str, option_labels: list[str]
) -> int | None:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        session = conn.execute(
            "SELECT id FROM sessions WHERE code = ?", (code,)
        ).fetchone()
        if session is None:
            conn.rollback()
            return None

        session_id = session["id"]
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM questions WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO questions (session_id, position, type, text) VALUES (?, ?, ?, ?)",
            (session_id, position, question_type, text),
        )
        question_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO options (question_id, position, label) VALUES (?, ?, ?)",
            (
                (question_id, option_position, label)
                for option_position, label in enumerate(option_labels, start=1)
            ),
        )
        conn.commit()
        return question_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_word_cloud_response(
    code: str, question_id: int, participant_id: str, text: str
) -> str:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        question = conn.execute(
            """SELECT q.type, q.is_open
               FROM questions AS q
               JOIN sessions AS s ON s.id = q.session_id
               WHERE s.code = ? AND q.id = ?""",
            (code, question_id),
        ).fetchone()
        if question is None:
            result = "not_found"
        elif question["type"] != "word_cloud":
            result = "wrong_type"
        elif not question["is_open"]:
            result = "closed"
        else:
            response_count = conn.execute(
                """SELECT COUNT(*) FROM responses
                   WHERE question_id = ? AND participant_id = ?""",
                (question_id, participant_id),
            ).fetchone()[0]
            if response_count >= 3:
                result = "limit_reached"
            else:
                created_at = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT INTO responses
                       (question_id, participant_id, text, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (question_id, participant_id, text, created_at),
                )
                conn.commit()
                return "saved"
        conn.rollback()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
