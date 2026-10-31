"""Saves the host's chosen slide order."""
from typing import Literal

from .db import connect

ReorderResult = Literal["ok", "not_found", "mismatch"]


def reorder_questions(code: str, question_ids: list[int]) -> ReorderResult:
    """Set positions 1..N in the given order. The list must be exactly the session's ids."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        session = conn.execute(
            "SELECT id FROM sessions WHERE code = ?", (code,)
        ).fetchone()
        if session is None:
            conn.rollback()
            return "not_found"

        rows = conn.execute(
            "SELECT id FROM questions WHERE session_id = ?", (session["id"],)
        ).fetchall()
        if sorted(question_ids) != sorted(row["id"] for row in rows):
            conn.rollback()
            return "mismatch"

        conn.executemany(
            "UPDATE questions SET position = ? WHERE id = ?",
            ((position, qid) for position, qid in enumerate(question_ids, start=1)),
        )
        conn.commit()
        return "ok"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
