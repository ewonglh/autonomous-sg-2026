import asyncio
import json
import os
import tempfile
import unittest

from src import db, routes
from src.limits import RateLimiter
from src.main import app


async def _call_app(method: str, path: str, headers: dict | None, body: dict | None):
    raw = json.dumps(body).encode() if body is not None else b""
    header_list = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    if body is not None:
        header_list.append((b"content-type", b"application/json"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "path": path, "raw_path": path.encode(), "query_string": b"",
        "headers": header_list, "client": ("test", 0), "server": ("test", 80),
        "scheme": "http", "root_path": "",
    }
    sent = [{"type": "http.request", "body": raw, "more_body": False}]

    async def receive():
        return sent.pop(0) if sent else {"type": "http.disconnect"}

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


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._original_rate_limiter = routes.rate_limiter
        routes.rate_limiter = RateLimiter()
        self._original_db_path = os.environ.get("DB_PATH")
        self._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._temp_dir.name, "test.db")
        db.init_db()

    def tearDown(self):
        routes.rate_limiter = self._original_rate_limiter
        if self._original_db_path is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = self._original_db_path
        self._temp_dir.cleanup()

    def request(self, method: str, path: str, headers: dict | None = None, body: dict | None = None):
        return asyncio.run(_call_app(method, path, headers, body))

    def create_session(self) -> dict:
        status, body, _ = self.request("POST", "/api/sessions")
        self.assertEqual(status, 200)
        return json.loads(body)
