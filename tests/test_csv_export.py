"""CSV export route tests using direct ASGI calls."""
import asyncio
import csv
import io
import os
import tempfile
import unittest

from src.db import connect, init_db
from src.auth import hash_host_key
from src.main import app


async def call(method, path, headers=None):
    header_list = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": b"", "headers": header_list,
        "client": ("test", 0), "server": ("test", 80), "scheme": "http", "root_path": "",
    }
    messages = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    status, chunks, response_headers = 0, [], {}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            response_headers.update({key.decode(): value.decode() for key, value in message["headers"]})
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return status, b"".join(chunks), response_headers


def request(*args, **kwargs):
    return asyncio.run(call(*args, **kwargs))


def parse_csv(data):
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))


class CsvExportTests(unittest.TestCase):
    def setUp(self):
        self.original_db_path = os.environ.get("DB_PATH")
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self.temp_dir.name, "test.db")
        init_db()
        conn = connect()
        conn.execute(
            "INSERT INTO sessions (code, host_key_hash, title, created_at, last_active_at) "
            "VALUES ('CSV123', ?, 'Test', '2026-10-31T00:00:00Z', '2026-10-31T00:00:00Z')",
            (hash_host_key("dummy"),),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        if self.original_db_path is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def test_export_escapes_fields_and_neutralises_formula_like_answer(self):
        conn = connect()
        question = conn.execute(
            "INSERT INTO questions (session_id, position, type, text) "
            "SELECT id, 1, 'word_cloud', ? FROM sessions WHERE code = 'CSV123'",
            ('Question, with "quotes" and\nnewline 😀',),
        )
        conn.execute(
            "INSERT INTO responses (question_id, participant_id, text, created_at) "
            "VALUES (?, ?, ?, ?)",
            (question.lastrowid, "participant-😀", '=answer, "quoted"\n😀', "2026-10-31T00:00:00Z"),
        )
        conn.commit()
        conn.close()

        status, body, headers = request(
            "GET", "/api/sessions/CSV123/export.csv", {"authorization": "Bearer dummy"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(headers["content-type"].startswith("text/csv"))
        rows = parse_csv(body)
        self.assertEqual(rows[0], [
            "session_code", "question_order", "question_type", "question_text",
            "answer", "participant_id", "submitted_at_utc", "qa_upvotes",
        ])
        self.assertEqual(rows[1], [
            "CSV123", "1", "word_cloud", 'Question, with "quotes" and\nnewline 😀',
            "'=answer, \"quoted\"\n😀", "participant-😀", "2026-10-31T00:00:00Z", "",
        ])

    def test_empty_session_has_header_only(self):
        status, body, _ = request(
            "GET", "/api/sessions/CSV123/export.csv", {"authorization": "Bearer dummy"}
        )
        self.assertEqual(status, 200)
        rows = parse_csv(body)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "session_code")

    def test_export_requires_host_key(self):
        self.assertEqual(request("GET", "/api/sessions/CSV123/export.csv")[0], 401)


if __name__ == "__main__":
    unittest.main()
