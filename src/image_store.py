"""Slide pictures: check uploads and keep one picture per slide."""
import base64
import binascii
import re

from .db import connect

MAX_DATA_URL_LENGTH = 1_500_000
DATA_URL = re.compile(r"data:(image/(?:png|jpeg|gif|webp));base64,(.+)", re.S)
# The first bytes of each allowed format. SVG is not allowed: it can carry scripts.
SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


def decode_data_url(data_url: str) -> tuple[str, bytes] | None:
    """Returns (media type, bytes), or None if this is not a real image data URL."""
    match = DATA_URL.fullmatch(data_url.strip())
    if match is None:
        return None
    media_type, encoded = match.groups()
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not data.startswith(SIGNATURES[media_type]):
        return None
    if media_type == "image/webp" and data[8:12] != b"WEBP":
        return None
    return media_type, data


def _question_in_session(conn, code: str, question_id: int) -> bool:
    row = conn.execute(
        """SELECT 1 FROM questions AS q JOIN sessions AS s ON s.id = q.session_id
           WHERE s.code = ? AND q.id = ?""",
        (code, question_id),
    ).fetchone()
    return row is not None


def save_image(code: str, question_id: int, media_type: str, data: bytes) -> bool:
    """False if the slide is not in this session. Replacing a picture bumps its version."""
    conn = connect()
    try:
        if not _question_in_session(conn, code, question_id):
            return False
        conn.execute(
            """INSERT INTO question_images (question_id, media_type, data) VALUES (?, ?, ?)
               ON CONFLICT (question_id) DO UPDATE SET
                   media_type = excluded.media_type, data = excluded.data,
                   version = question_images.version + 1""",
            (question_id, media_type, data),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_image(code: str, question_id: int) -> bool:
    """False if the slide is not in this session. Deleting a missing picture is fine."""
    conn = connect()
    try:
        if not _question_in_session(conn, code, question_id):
            return False
        conn.execute("DELETE FROM question_images WHERE question_id = ?", (question_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def load_image(code: str, question_id: int) -> tuple[str, bytes] | None:
    conn = connect()
    try:
        row = conn.execute(
            """SELECT i.media_type, i.data FROM question_images AS i
               JOIN questions AS q ON q.id = i.question_id
               JOIN sessions AS s ON s.id = q.session_id
               WHERE s.code = ? AND i.question_id = ?""",
            (code, question_id),
        ).fetchone()
        return (row["media_type"], row["data"]) if row else None
    finally:
        conn.close()


def image_urls(code: str) -> dict[int, str]:
    """Picture URL for each slide in the session that has one. The version changes the URL
    whenever the picture changes, so screens never show a stale cached copy."""
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT i.question_id, i.version FROM question_images AS i
               JOIN questions AS q ON q.id = i.question_id
               JOIN sessions AS s ON s.id = q.session_id
               WHERE s.code = ?""",
            (code,),
        ).fetchall()
        return {
            row["question_id"]: (
                f"/api/sessions/{code}/questions/{row['question_id']}/image?v={row['version']}"
            )
            for row in rows
        }
    finally:
        conn.close()
