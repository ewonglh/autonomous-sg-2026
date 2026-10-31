import json
import uuid

from src import db
from support import ApiTestCase


class EditDeleteSlideTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.base = f"/api/sessions/{self.code}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}

    def make(self, text="Q?", kind="multiple_choice", options=("A", "B")):
        _, raw, _ = self.request(
            "POST", f"{self.base}/questions", self.host,
            {"type": kind, "text": text, "options": list(options) if kind == "multiple_choice" else []},
        )
        return json.loads(raw)["id"]

    def activate(self, qid):
        self.request("POST", f"{self.base}/active", self.host, {"question_id": qid})

    def active(self):
        _, raw, _ = self.request("GET", f"{self.base}/state")
        return json.loads(raw)["active_question"]

    def patch(self, qid, body, headers=None):
        status, raw, _ = self.request("PATCH", f"{self.base}/questions/{qid}", headers or self.host, body)
        return status, json.loads(raw)

    def positions(self):
        conn = db.connect()
        try:
            return [r["position"] for r in conn.execute(
                "SELECT position FROM questions ORDER BY position")]
        finally:
            conn.close()

    def vote(self, qid):
        option = db.connect().execute("SELECT id FROM options WHERE question_id = ?", (qid,)).fetchone()["id"]
        return self.request(
            "POST", f"{self.base}/questions/{qid}/responses",
            {"x-participant-id": str(uuid.uuid4())}, {"option_id": option},
        )[0]

    def test_edit_text_shows_in_state(self):
        qid = self.make()
        self.activate(qid)
        self.assertEqual(self.patch(qid, {"text": "  Fixed?  "})[0], 200)
        self.assertEqual(self.active()["text"], "Fixed?")

    def test_edit_options_before_any_vote(self):
        qid = self.make()
        self.activate(qid)
        self.assertEqual(self.patch(qid, {"options": ["X", "Y", "Z"]})[0], 200)
        self.assertEqual([o["label"] for o in self.active()["options"]], ["X", "Y", "Z"])

    def test_edit_options_rejected_after_a_vote(self):
        qid = self.make()
        self.assertEqual(self.vote(qid), 200)
        status, body = self.patch(qid, {"options": ["X", "Y"]})
        self.assertEqual((status, body["code"]), (409, "has_responses"))
        self.assertEqual(self.patch(qid, {"text": "Still editable?"})[0], 200)

    def test_edit_limits_and_flags_still_work(self):
        qid = self.make()
        self.assertEqual(self.patch(qid, {"text": "x" * 301})[0], 422)
        self.assertEqual(self.patch(qid, {"options": ["Only"]})[0], 422)
        self.assertEqual(self.patch(qid, {"options": ["a", "A"]})[0], 422)
        self.assertEqual(self.patch(qid, {"text": "T", "is_open": False})[0], 200)

    def test_options_on_word_cloud_rejected(self):
        qid = self.make(kind="word_cloud")
        status, body = self.patch(qid, {"options": ["A", "B"]})
        self.assertEqual((status, body["code"]), (422, "wrong_type"))

    def test_delete_middle_slide_renumbers(self):
        first, middle, last = self.make("1"), self.make("2"), self.make("3")
        status, _, _ = self.request("DELETE", f"{self.base}/questions/{middle}", self.host)
        self.assertEqual(status, 200)
        self.assertEqual(self.positions(), [1, 2])
        _, raw, _ = self.request("POST", f"{self.base}/questions", self.host,
                                 {"type": "word_cloud", "text": "4"})
        self.assertEqual(self.positions(), [1, 2, 3])

    def test_delete_removes_options_and_responses(self):
        qid = self.make()
        self.vote(qid)
        self.request("DELETE", f"{self.base}/questions/{qid}", self.host)
        conn = db.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM options").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 0)
        conn.close()

    def test_delete_slide_on_screen_clears_active(self):
        qid = self.make()
        other = self.make("other")
        self.activate(qid)
        self.request("DELETE", f"{self.base}/questions/{qid}", self.host)
        self.assertIsNone(self.active())
        self.activate(other)
        self.request("DELETE", f"{self.base}/questions/{self.make('x')}", self.host)
        self.assertEqual(self.active()["id"], other)

    def test_auth_and_not_found(self):
        qid = self.make()
        stranger = self.create_session()
        wrong = {"authorization": f"Bearer {stranger['host_key']}"}
        for method, body in (("PATCH", {"text": "x"}), ("DELETE", None)):
            path = f"{self.base}/questions/{qid}"
            self.assertEqual(self.request(method, path, wrong, body)[0], 401)
            self.assertEqual(self.request(method, f"{self.base}/questions/999", self.host, body)[0], 404)
