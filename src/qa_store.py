"""SQL for Q&A slides: audience questions and their upvotes."""
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from .db import connect

PostResult = Literal["not_found", "closed"] | int
UpvoteResult = Literal["ok", "not_found", "duplicate"]


def _qa_slide(conn: sqlite3.Connection, code: str, question_id: int):
    return conn.execute(
        """SELECT q.id, q.is_open FROM questions AS q
           JOIN sessions AS s ON s.id = q.session_id
           WHERE s.code = ? AND q.id = ? AND q.type = 'qa'""",
        (code, question_id),
    ).fetchone()


def _item_exists(conn: sqlite3.Connection, code: str, question_id: int, item_id: int) -> bool:
    if _qa_slide(conn, code, question_id) is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM qa_items WHERE id = ? AND question_id = ?", (item_id, question_id)
    ).fetchone()
    return row is not None


def list_items(code: str, question_id: int, participant_id: str | None) -> list[dict] | None:
    """Items on one Q&A slide, most upvoted first. None if it is not a Q&A slide here."""
    conn = connect()
    try:
        if _qa_slide(conn, code, question_id) is None:
            return None
        rows = conn.execute(
            """SELECT i.id, i.text, COUNT(u.qa_item_id) AS upvotes,
                      COALESCE(MAX(u.participant_id = ?), 0) AS upvoted_by_me
               FROM qa_items AS i
               LEFT JOIN qa_upvotes AS u ON u.qa_item_id = i.id
               WHERE i.question_id = ?
               GROUP BY i.id
               ORDER BY upvotes DESC, i.id""",
            (participant_id, question_id),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "text": row["text"],
                "upvotes": row["upvotes"],
                "upvoted_by_me": bool(row["upvoted_by_me"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def add_item(code: str, question_id: int, participant_id: str, text: str) -> PostResult:
    """Returns the new item id, or why it was refused."""
    conn = connect()
    try:
        slide = _qa_slide(conn, code, question_id)
        if slide is None:
            return "not_found"
        if not slide["is_open"]:
            return "closed"
        cursor = conn.execute(
            """INSERT INTO qa_items (question_id, participant_id, text, created_at)
               VALUES (?, ?, ?, ?)""",
            (question_id, participant_id, text, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def add_upvote(code: str, question_id: int, item_id: int, participant_id: str) -> UpvoteResult:
    """Upvotes work even when the slide is closed."""
    conn = connect()
    try:
        if not _item_exists(conn, code, question_id, item_id):
            return "not_found"
        try:
            conn.execute(
                "INSERT INTO qa_upvotes (qa_item_id, participant_id) VALUES (?, ?)",
                (item_id, participant_id),
            )
        except sqlite3.IntegrityError:
            return "duplicate"
        conn.commit()
        return "ok"
    finally:
        conn.close()


def remove_upvote(code: str, question_id: int, item_id: int, participant_id: str) -> bool:
    """False if the item does not exist; removing a missing upvote is not an error."""
    conn = connect()
    try:
        if not _item_exists(conn, code, question_id, item_id):
            return False
        conn.execute(
            "DELETE FROM qa_upvotes WHERE qa_item_id = ? AND participant_id = ?",
            (item_id, participant_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()
