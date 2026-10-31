import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Literal

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

SESSION_IDLE_TIMEOUT = timedelta(hours=24)

ResponseSubmission = Literal[
    "accepted", "not_found", "wrong_type", "closed", "invalid_option", "duplicate"
]


def db_path() -> str:
    return os.environ.get("DB_PATH", "crowdpulse.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def has_session_expired(last_active_at: str, now: datetime | None = None) -> bool:
    if last_active_at.endswith("Z"):
        last_active_at = f"{last_active_at[:-1]}+00:00"
    last_active = datetime.fromisoformat(last_active_at)
    current_time = utc_now() if now is None else now
    return current_time - last_active >= SESSION_IDLE_TIMEOUT


def session_is_expired(code: str) -> bool:
    conn = connect()
    try:
        session = conn.execute(
            "SELECT last_active_at FROM sessions WHERE code = ?", (code,)
        ).fetchone()
        return session is not None and has_session_expired(session["last_active_at"])
    finally:
        conn.close()


def touch_session_activity(code: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE sessions SET last_active_at = ? WHERE code = ?",
            (utc_now().isoformat(), code),
        )
        conn.commit()
    finally:
        conn.close()


def create_session(code: str, host_key_hash: str) -> bool:
    now = utc_now().isoformat()
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


def save_multiple_choice_response(
    code: str, question_id: int, participant_id: str, option_id: int
) -> ResponseSubmission:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        question = conn.execute(
            """SELECT q.type, q.is_open
               FROM questions q
               JOIN sessions s ON s.id = q.session_id
               WHERE s.code = ? AND q.id = ?""",
            (code, question_id),
        ).fetchone()
        if question is None:
            return "not_found"
        if question["type"] != "multiple_choice":
            return "wrong_type"
        if not question["is_open"]:
            return "closed"

        option = conn.execute(
            "SELECT 1 FROM options WHERE id = ? AND question_id = ?",
            (option_id, question_id),
        ).fetchone()
        if option is None:
            return "invalid_option"

        try:
            conn.execute(
                """INSERT INTO responses
                   (question_id, participant_id, option_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    question_id,
                    participant_id,
                    option_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return "accepted"
        except sqlite3.IntegrityError:
            conn.rollback()
            duplicate = conn.execute(
                """SELECT 1 FROM responses
                   WHERE question_id = ? AND participant_id = ? AND option_id IS NOT NULL""",
                (question_id, participant_id),
            ).fetchone()
            if duplicate is not None:
                return "duplicate"
            raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_question_state(code: str, question_id: int, changes: dict[str, bool]) -> bool:
    allowed_fields = {"is_open", "results_visible"}
    if not changes or not set(changes).issubset(allowed_fields):
        raise ValueError("Question state changes must contain valid flags")

    assignments = ", ".join(f"{field} = ?" for field in changes)
    values = [int(value) for value in changes.values()]
    conn = connect()
    try:
        cursor = conn.execute(
            f"""UPDATE questions SET {assignments}
                WHERE id = ? AND session_id = (
                    SELECT id FROM sessions WHERE code = ?
                )""",
            (*values, question_id, code),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def set_active_question(code: str, question_id: int) -> bool:
    conn = connect()
    try:
        cursor = conn.execute(
            """UPDATE sessions SET active_question_id = ?
               WHERE code = ? AND EXISTS (
                   SELECT 1 FROM questions
                   WHERE questions.id = ? AND questions.session_id = sessions.id
               )""",
            (question_id, code, question_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def get_session_state(code: str) -> dict | None:
    conn = connect()
    try:
        session = conn.execute(
            """SELECT sessions.title, questions.id AS question_id, questions.type,
                      questions.text, questions.is_open, questions.results_visible
               FROM sessions
               LEFT JOIN questions
                 ON questions.id = sessions.active_question_id
                AND questions.session_id = sessions.id
               WHERE sessions.code = ?""",
            (code,),
        ).fetchone()
        if session is None:
            return None

        active_question = None
        if session["question_id"] is not None:
            options = conn.execute(
                "SELECT id, label FROM options WHERE question_id = ? ORDER BY position",
                (session["question_id"],),
            ).fetchall()
            active_question = {
                "id": session["question_id"],
                "type": session["type"],
                "text": session["text"],
                "options": [{"id": row["id"], "label": row["label"]} for row in options],
                "is_open": bool(session["is_open"]),
                "results_visible": bool(session["results_visible"]),
            }
        return {"title": session["title"], "active_question": active_question}
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


def get_session_results(code: str) -> list[dict]:
    conn = connect()
    try:
        questions = conn.execute(
            """SELECT q.id, q.type
               FROM questions AS q
               JOIN sessions AS s ON s.id = q.session_id
               WHERE s.code = ?
               ORDER BY q.position""",
            (code,),
        ).fetchall()

        results = []
        for question in questions:
            question_id = question["id"]
            if question["type"] == "multiple_choice":
                options = conn.execute(
                    """SELECT o.id AS option_id, o.label, COUNT(r.id) AS count
                       FROM options AS o
                       LEFT JOIN responses AS r
                         ON r.option_id = o.id AND r.question_id = o.question_id
                       WHERE o.question_id = ?
                       GROUP BY o.id, o.label, o.position
                       ORDER BY o.position""",
                    (question_id,),
                ).fetchall()
                results.append(
                    {
                        "question_id": question_id,
                        "type": question["type"],
                        "options": [dict(option) for option in options],
                    }
                )
                continue

            responses = conn.execute(
                """SELECT text FROM responses
                   WHERE question_id = ? AND text IS NOT NULL
                   ORDER BY created_at, id""",
                (question_id,),
            ).fetchall()
            words_by_key = {}
            for response in responses:
                word = response["text"].strip()
                key = word.casefold()
                if key not in words_by_key:
                    words_by_key[key] = {"word": word, "count": 0}
                words_by_key[key]["count"] += 1

            results.append(
                {
                    "question_id": question_id,
                    "type": question["type"],
                    "words": list(words_by_key.values()),
                }
            )
        return results
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
