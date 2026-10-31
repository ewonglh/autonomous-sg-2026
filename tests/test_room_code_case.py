import asyncio
import json

from src.main import app
from support import ApiTestCase


async def _ws_first_message(path: str) -> dict:
    scope = {
        "type": "websocket", "asgi": {"version": "3.0"}, "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [], "scheme": "ws", "root_path": "", "subprotocols": [],
        "client": ("test", 0), "server": ("test", 80),
    }
    inbox = [{"type": "websocket.connect"}]
    sent = []

    async def receive():
        return inbox.pop(0) if inbox else {"type": "websocket.disconnect", "code": 1000}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return {"types": [m["type"] for m in sent], "text": next((m.get("text") for m in sent if m.get("text")), None)}


class RoomCodeCaseTests(ApiTestCase):
    def test_public_route_accepts_lowercase_mixed_case_and_spaces(self):
        code = self.create_session()["code"]
        for variant in (code.lower(), code[:4].lower() + code[4:], f" {code.lower()} "):
            status, body, _ = self.request("GET", f"/api/sessions/{variant}/state")
            self.assertEqual(status, 200, variant)
            self.assertIn("active_question", json.loads(body))

    def test_host_route_accepts_lowercase_code_with_host_key(self):
        session = self.create_session()
        headers = {"authorization": f"Bearer {session['host_key']}"}
        status, _, _ = self.request(
            "POST", f"/api/sessions/{session['code'].lower()}/questions", headers,
            {"type": "word_cloud", "text": "Hi?"},
        )
        self.assertEqual(status, 200)

    def test_unknown_code_is_still_not_found(self):
        self.assertEqual(self.request("GET", "/api/sessions/nope1234/state")[0], 404)

    def test_websocket_accepts_lowercase_code(self):
        code = self.create_session()["code"]
        result = asyncio.run(_ws_first_message(f"/ws/{code.lower()}"))
        self.assertIn("websocket.accept", result["types"])
        self.assertEqual(json.loads(result["text"]), {"type": "question_changed"})
