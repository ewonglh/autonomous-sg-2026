"""Contract-shape tests. Call the ASGI app directly so no extra dependency is needed."""
import asyncio
import json
import os
import tempfile
import unittest

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from src.main import app  # noqa: E402
from src.db import connect, init_db  # noqa: E402

init_db()
_conn = connect()
_conn.execute(
    "INSERT OR IGNORE INTO sessions (code, host_key_hash, title, created_at, last_active_at) "
    "VALUES ('ABC123', 'unused', 'Test session', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
)
_conn.commit()
_conn.close()

HOST = {"authorization": "Bearer dummy-host-key"}


async def call(method: str, path: str, headers: dict | None = None, body: dict | None = None):
    raw = json.dumps(body).encode() if body is not None else b""
    header_list = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if body is not None:
        header_list.append((b"content-type", b"application/json"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": b"", "headers": header_list,
        "client": ("test", 0), "server": ("test", 80), "scheme": "http", "root_path": "",
    }
    sent = [{"type": "http.request", "body": raw, "more_body": False}]

    async def receive():
        return sent.pop(0) if sent else {"type": "http.disconnect"}

    status, chunks, resp_headers = 0, [], {}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            resp_headers.update({k.decode(): v.decode() for k, v in message["headers"]})
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return status, b"".join(chunks), resp_headers


def request(*args, **kwargs):
    return asyncio.run(call(*args, **kwargs))


class ContractTests(unittest.TestCase):
    def test_healthz(self):
        status, body, _ = request("GET", "/healthz")
        self.assertEqual((status, json.loads(body)), (200, {"status": "ok"}))

    def test_create_session(self):
        status, body, _ = request("POST", "/api/sessions")
        self.assertEqual(status, 200)
        self.assertEqual(set(json.loads(body)), {"code", "host_key"})

    def test_state_shape(self):
        status, body, _ = request("GET", "/api/sessions/ABC123/state")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"title", "active_question"})
        question = data["active_question"]
        self.assertEqual(
            set(question), {"id", "type", "text", "options", "is_open", "results_visible"}
        )
        self.assertEqual(set(question["options"][0]), {"id", "label"})

    def test_host_routes_need_bearer_key(self):
        for method, path in [
            ("GET", "/api/sessions/ABC123/results"),
            ("GET", "/api/sessions/ABC123/export.csv"),
        ]:
            self.assertEqual(request(method, path)[0], 401)
            self.assertEqual(request(method, path, HOST)[0], 200)

    def test_results_shape(self):
        _, body, _ = request("GET", "/api/sessions/ABC123/results", HOST)
        results = json.loads(body)["results"]
        self.assertEqual(set(results[0]["options"][0]), {"option_id", "label", "count"})
        self.assertEqual(set(results[1]["words"][0]), {"word", "count"})

    def test_response_needs_participant_header(self):
        path = "/api/sessions/ABC123/questions/1/responses"
        self.assertEqual(request("POST", path, None, {"option_id": 1})[0], 422)
        headers = {"x-participant-id": "11111111-1111-1111-1111-111111111111"}
        self.assertEqual(request("POST", path, headers, {"option_id": 1})[0], 200)

    def test_csv_header_columns(self):
        _, body, headers = request("GET", "/api/sessions/ABC123/export.csv", HOST)
        self.assertTrue(headers["content-type"].startswith("text/csv"))
        self.assertEqual(
            body.decode("utf-8-sig").strip().split(","),
            ["session_code", "question_order", "question_type", "question_text",
             "answer", "participant_id", "submitted_at_utc", "qa_upvotes"],
        )


if __name__ == "__main__":
    unittest.main()
