import json
import uuid

from src import db
from support import ApiTestCase


class ErrorCodeTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.base = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.poll = self.make_question("multiple_choice", ["Yes", "No"])
        self.cloud = self.make_question("word_cloud")
        self.voter = {"x-participant-id": str(uuid.uuid4())}

    def make_question(self, kind, options=None):
        body = {"type": kind, "text": "Q?", "options": options or []}
        status, raw, _ = self.request("POST", f"{self.base}/questions", self.host, body)
        self.assertEqual(status, 200)
        return json.loads(raw)["id"]

    def option_id(self, question_id):
        conn = db.connect()
        try:
            return conn.execute(
                "SELECT id FROM options WHERE question_id = ?", (question_id,)
            ).fetchone()["id"]
        finally:
            conn.close()

    def close(self, question_id):
        self.request("PATCH", f"{self.base}/questions/{question_id}", self.host, {"is_open": False})

    def answer(self, question_id, body, headers=None):
        status, raw, _ = self.request(
            "POST", f"{self.base}/questions/{question_id}/responses",
            headers or self.voter, body,
        )
        return status, json.loads(raw)

    def assert_rejected(self, result, status, code):
        self.assertEqual(result[0], status)
        self.assertEqual(result[1]["code"], code)
        self.assertTrue(result[1]["detail"])

    def test_repeat_vote_is_already_responded(self):
        body = {"option_id": self.option_id(self.poll)}
        self.assertEqual(self.answer(self.poll, body)[0], 200)
        self.assert_rejected(self.answer(self.poll, body), 409, "already_responded")

    def test_closed_slide_is_403_closed(self):
        self.close(self.poll)
        self.close(self.cloud)
        self.assert_rejected(self.answer(self.poll, {"option_id": self.option_id(self.poll)}), 403, "closed")
        self.assert_rejected(self.answer(self.cloud, {"text": "hi"}), 403, "closed")

    def test_word_limit_is_429_limit_reached(self):
        for word in ("a", "b", "c"):
            self.assertEqual(self.answer(self.cloud, {"text": word})[0], 200)
        self.assert_rejected(self.answer(self.cloud, {"text": "d"}), 429, "limit_reached")

    def test_wrong_kind_of_answer_is_422_wrong_type(self):
        self.assert_rejected(self.answer(self.cloud, {"option_id": self.option_id(self.poll)}), 422, "wrong_type")
        self.assert_rejected(self.answer(self.poll, {"text": "hi"}), 422, "wrong_type")

    def test_unknown_slide_is_404_not_found(self):
        self.assert_rejected(self.answer(9999, {"text": "hi"}), 404, "not_found")
        self.assert_rejected(self.answer(9999, {"option_id": 1}), 404, "not_found")
