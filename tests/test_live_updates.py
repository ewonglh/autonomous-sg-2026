import asyncio
import json

from src import db
from src.main import app
from support import ApiTestCase, _call_app


async def connect_websocket(path: str):
    incoming = asyncio.Queue()
    outgoing = asyncio.Queue()
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("test", 0),
        "server": ("test", 80),
        "subprotocols": [],
        "root_path": "",
    }

    async def receive():
        return await incoming.get()

    async def send(message):
        await outgoing.put(message)

    task = asyncio.create_task(app(scope, receive, send))
    await incoming.put({"type": "websocket.connect"})
    accepted = await asyncio.wait_for(outgoing.get(), timeout=1)
    if accepted["type"] != "websocket.accept":
        raise AssertionError(f"Unexpected WebSocket response: {accepted}")
    return task, incoming, outgoing


async def disconnect_websocket(task, incoming):
    await incoming.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(task, timeout=1)


async def receive_event(outgoing) -> str:
    message = await asyncio.wait_for(outgoing.get(), timeout=1)
    if message["type"] != "websocket.send":
        raise AssertionError(f"Unexpected WebSocket response: {message}")
    return json.loads(message["text"])["type"]


class LiveUpdateTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.base = f"/api/sessions/{self.code}"

    def test_question_changes_are_broadcast(self):
        async def scenario():
            task, incoming, outgoing = await connect_websocket(f"/ws/{self.code}")
            try:
                question_body = {
                    "type": "multiple_choice",
                    "text": "Ready?",
                    "options": ["Yes", "No"],
                }
                status, body, _ = await _call_app(
                    "POST",
                    f"{self.base}/questions",
                    self.host,
                    question_body,
                )
                self.assertEqual(status, 200)
                question_id = json.loads(body)["id"]
                self.assertEqual(await receive_event(outgoing), "question_changed")

                status, _, _ = await _call_app(
                    "PATCH",
                    f"{self.base}/questions/{question_id}",
                    self.host,
                    {"results_visible": True},
                )
                self.assertEqual(status, 200)
                self.assertEqual(await receive_event(outgoing), "question_changed")

                status, _, _ = await _call_app(
                    "POST",
                    f"{self.base}/active",
                    self.host,
                    {"question_id": question_id},
                )
                self.assertEqual(status, 200)
                self.assertEqual(await receive_event(outgoing), "question_changed")
            finally:
                await disconnect_websocket(task, incoming)

        asyncio.run(scenario())

    def test_each_accepted_response_broadcasts_results_changed(self):
        choice_id = db.create_question(
            self.code, "multiple_choice", "Pick one?", ["A", "B"]
        )
        word_id = db.create_question(self.code, "word_cloud", "One word?", [])

        async def scenario():
            task, incoming, outgoing = await connect_websocket(f"/ws/{self.code}")
            try:
                for question_id, body in (
                    (choice_id, {"option_id": 1}),
                    (word_id, {"text": "A thought"}),
                ):
                    status, _, _ = await _call_app(
                        "POST",
                        f"{self.base}/questions/{question_id}/responses",
                        {"x-participant-id": "11111111-1111-1111-1111-111111111111"},
                        body,
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(await receive_event(outgoing), "results_changed")
            finally:
                await disconnect_websocket(task, incoming)

        asyncio.run(scenario())
