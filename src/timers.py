"""Slide timers: start and stop them, and close slides whose time is up."""
import math
from datetime import datetime, timedelta

from .db import connect, utc_now


def _stamp(moment: datetime) -> str:
    # Fixed width so stored times compare correctly as text.
    return moment.isoformat(timespec="microseconds")


def start_timer(code: str, question_id: int) -> None:
    """If the slide has a time limit, open it, hide its results and start the countdown.

    Calling it again restarts the countdown. Q&A slides keep their results flag.
    """
    conn = connect()
    try:
        row = conn.execute(
            """SELECT q.id, q.time_limit FROM questions AS q
               JOIN sessions AS s ON s.id = q.session_id
               WHERE s.code = ? AND q.id = ?""",
            (code, question_id),
        ).fetchone()
        if row is None or row["time_limit"] is None:
            return
        closes_at = _stamp(utc_now() + timedelta(seconds=row["time_limit"]))
        conn.execute(
            """UPDATE questions SET is_open = 1, closes_at = ?,
                   results_visible = CASE WHEN type = 'qa' THEN results_visible ELSE 0 END
               WHERE id = ?""",
            (closes_at, row["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def stop_timer(code: str, question_id: int) -> None:
    conn = connect()
    try:
        conn.execute(
            """UPDATE questions SET closes_at = NULL
               WHERE id = ? AND session_id = (SELECT id FROM sessions WHERE code = ?)""",
            (question_id, code),
        )
        conn.commit()
    finally:
        conn.close()


def is_showing(code: str, question_id: int) -> bool:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE code = ? AND active_question_id = ?",
            (code, question_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def close_expired() -> list[str]:
    """Close every slide whose time is up and reveal its results.

    Returns the codes of the sessions that changed, so their screens can be told.
    """
    now = _stamp(utc_now())
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT DISTINCT s.code FROM questions AS q
               JOIN sessions AS s ON s.id = q.session_id
               WHERE q.closes_at IS NOT NULL AND q.closes_at <= ?""",
            (now,),
        ).fetchall()
        if not rows:
            return []
        conn.execute(
            """UPDATE questions SET is_open = 0, closes_at = NULL,
                   results_visible = CASE WHEN type = 'qa' THEN results_visible ELSE 1 END
               WHERE closes_at IS NOT NULL AND closes_at <= ?""",
            (now,),
        )
        conn.commit()
        return [row["code"] for row in rows]
    finally:
        conn.close()


def add_seconds_left(question: dict) -> None:
    """Replace the stored closing time with whole seconds left, or None when no timer runs."""
    closes_at = question.pop("closes_at", None)
    if closes_at is None or not question["is_open"]:
        question["seconds_left"] = None
        return
    left = (datetime.fromisoformat(closes_at) - utc_now()).total_seconds()
    question["seconds_left"] = max(0, math.ceil(left))
