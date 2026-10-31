import json
import sqlite3
import uuid
from unittest import mock

from src import db
from support import ApiTestCase


class QaTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.base = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.alice = {"x-participant-id": str(uuid.uuid4())}
        self.bob = {"x-participant-id": str(uuid.uuid4())}
        self.slide = self.create_slide("qa")

    def create_slide(self, slide_type, **extra):
        status, raw, _ = self.request(
            "POST", f"{self.base}/questions", self.host,
            {"type": slide_type, "text": "Ask us", **extra},
        )
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["id"]

    def qa_path(self, slide=None):
        return f"{self.base}/questions/{slide or self.slide}/qa"

    def ask(self, text="Why?", who=None, slide=None):
        return self.request("POST", self.qa_path(slide), who or self.alice, {"text": text})

    def items(self, who=None, slide=None):
        status, raw, _ = self.request("GET", self.qa_path(slide), who)
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["items"]

    def vote(self, method, item_id, who):
        status, _, _ = self.request(method, f"{self.qa_path()}/{item_id}/upvote", who)
        return status

    def test_posted_question_has_zero_upvotes(self):
        status, raw, _ = self.ask("  <b>Why?</b>  ")
        self.assertEqual(status, 200)
        item_id = json.loads(raw)["id"]
        self.assertEqual(
            self.items(),
            [{"id": item_id, "text": "<b>Why?</b>", "upvotes": 0, "upvoted_by_me": False}],
        )

    def test_upvote_counts_once_per_participant(self):
        item_id = json.loads(self.ask()[1])["id"]
        self.assertEqual(self.vote("POST", item_id, self.bob), 200)
        self.assertEqual(self.vote("POST", item_id, self.bob), 409)
        self.assertEqual(self.items(self.bob)[0]["upvotes"], 1)
        self.assertTrue(self.items(self.bob)[0]["upvoted_by_me"])
        self.assertFalse(self.items(self.alice)[0]["upvoted_by_me"])

    def test_remove_upvote_then_upvote_again(self):
        item_id = json.loads(self.ask()[1])["id"]
        self.assertEqual(self.vote("DELETE", item_id, self.bob), 200)  # no upvote yet: fine
        self.vote("POST", item_id, self.bob)
        self.assertEqual(self.vote("DELETE", item_id, self.bob), 200)
        self.assertEqual(self.items(self.bob)[0]["upvotes"], 0)
        self.assertFalse(self.items(self.bob)[0]["upvoted_by_me"])
        self.assertEqual(self.vote("POST", item_id, self.bob), 200)
        self.assertEqual(self.vote("DELETE", 999, self.bob), 404)

    def test_items_sorted_by_upvotes(self):
        first = json.loads(self.ask("First")[1])["id"]
        second = json.loads(self.ask("Second")[1])["id"]
        self.vote("POST", second, self.bob)
        self.assertEqual([item["id"] for item in self.items()], [second, first])

    def test_closed_slide_refuses_questions_but_allows_upvotes(self):
        item_id = json.loads(self.ask()[1])["id"]
        self.request(
            "PATCH", f"{self.base}/questions/{self.slide}", self.host, {"is_open": False}
        )
        self.assertEqual(self.ask("Late?")[0], 400)
        self.assertEqual(self.vote("POST", item_id, self.bob), 200)

    def test_slides_keep_separate_lists(self):
        other = self.create_slide("qa")
        self.ask("On first")
        self.assertEqual(self.items(slide=other), [])
        item_id = json.loads(self.ask("On first")[1])["id"]
        status, _, _ = self.request(
            "POST", f"{self.qa_path(other)}/{item_id}/upvote", self.bob
        )
        self.assertEqual(status, 404)

    def test_text_must_be_1_to_280_chars(self):
        for text in ("", "   ", "x" * 281):
            self.assertEqual(self.ask(text)[0], 422, text)
        self.assertEqual(self.ask("x" * 280)[0], 200)

    def test_non_qa_slide_is_404(self):
        cloud = self.create_slide("word_cloud")
        self.assertEqual(self.ask(slide=cloud)[0], 404)
        status, _, _ = self.request("GET", self.qa_path(cloud))
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", f"/api/sessions/NOPE/questions/{self.slide}/qa")
        self.assertEqual(status, 404)

    def test_response_count_is_number_of_questions(self):
        self.ask("One")
        self.ask("Two", self.bob)
        self.request("POST", f"{self.base}/active", self.host, {"question_id": self.slide})
        _, raw, _ = self.request("GET", f"{self.base}/state")
        self.assertEqual(json.loads(raw)["active_question"]["response_count"], 2)

    def test_changes_broadcast_qa_changed(self):
        with mock.patch("src.qa.publish_event", new=mock.AsyncMock()) as publish:
            item_id = json.loads(self.ask()[1])["id"]
            self.vote("POST", item_id, self.bob)
            self.vote("DELETE", item_id, self.bob)
            self.assertEqual(self.ask("", self.bob)[0], 422)
        code = self.session["code"]
        self.assertEqual(publish.await_args_list, [mock.call(code, "qa_changed")] * 3)

    def test_expired_session_hides_qa_and_ordering(self):
        conn = sqlite3.connect(db.db_path())
        try:
            conn.execute(
                "UPDATE sessions SET last_active_at = '2000-01-01T00:00:00+00:00'"
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.request("GET", self.qa_path())[0], 404)
        self.assertEqual(self.ask()[0], 404)
        status, _, _ = self.request(
            "PUT", f"{self.base}/questions/order", self.host,
            {"question_ids": [self.slide]},
        )
        self.assertEqual(status, 404)

    def test_deleting_qa_slide_removes_its_questions(self):
        item_id = json.loads(self.ask()[1])["id"]
        self.vote("POST", item_id, self.bob)
        status, _, _ = self.request(
            "DELETE", f"{self.base}/questions/{self.slide}", self.host
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.request("GET", self.qa_path())[0], 404)

    def test_room_code_any_case(self):
        self.ask()
        path = self.qa_path().replace(self.session["code"], self.session["code"].lower())
        status, raw, _ = self.request("GET", path)
        self.assertEqual((status, len(json.loads(raw)["items"])), (200, 1))
