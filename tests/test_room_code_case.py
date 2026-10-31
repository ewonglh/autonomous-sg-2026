import asyncio
import json

from support import ApiTestCase, _call_app
from test_live_updates import connect_websocket, disconnect_websocket, receive_event


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

    def test_websocket_with_lowercase_code_gets_room_broadcasts(self):
        session = self.create_session()
        code = session["code"]
        host = {"authorization": f"Bearer {session['host_key']}"}

        async def scenario():
            task, incoming, outgoing = await connect_websocket(f"/ws/{code.lower()}")
            try:
                status, _, _ = await _call_app(
                    "POST", f"/api/sessions/{code}/questions", host,
                    {"type": "word_cloud", "text": "Hi?"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(await receive_event(outgoing), "question_changed")
            finally:
                await disconnect_websocket(task, incoming)

        asyncio.run(scenario())
