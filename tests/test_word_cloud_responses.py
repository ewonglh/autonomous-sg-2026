import json
import sqlite3
import uuid

from src import db
from support import ApiTestCase


class WordCloudResponseTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.session_path = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        status, body, _ = self.request(
            "POST",
            f"{self.session_path}/questions",
            self.host,
            {"type": "word_cloud", "text": "What do you think?"},
        )
        self.assertEqual(status, 200)
        self.question_id = json.loads(body)["id"]
        self.response_path = (
            f"{self.session_path}/questions/{self.question_id}/responses"
        )
        self.participant_id = str(uuid.uuid4())
        self.participant = {"x-participant-id": self.participant_id}

    def stored_responses(self, question_id=None):
        question_id = question_id or self.question_id
        conn = sqlite3.connect(db.db_path())
        try:
            return conn.execute(
                "SELECT participant_id, text FROM responses WHERE question_id = ?",
                (question_id,),
            ).fetchall()
        finally:
            conn.close()

    def test_accepts_text_and_stores_it_without_html_conversion(self):
        answer = "<b>Nice place</b>"
        status, body, _ = self.request(
            "POST", self.response_path, self.participant, {"text": answer}
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertEqual(
            self.stored_responses(), [(self.participant_id, answer)]
        )

    def test_allows_three_responses_and_rejects_a_fourth(self):
        for answer in ("First", "Second", "Third"):
            status, _, _ = self.request(
                "POST", self.response_path, self.participant, {"text": answer}
            )
            self.assertEqual(status, 200)

        status, _, _ = self.request(
            "POST", self.response_path, self.participant, {"text": "Fourth"}
        )

        self.assertEqual(status, 429)
        self.assertEqual(len(self.stored_responses()), 3)

    def test_rejects_blank_and_overlong_text_without_storing(self):
        for answer in ("", "   ", "a" * 201):
            status, _, _ = self.request(
                "POST", self.response_path, self.participant, {"text": answer}
            )
            self.assertEqual(status, 422)

        self.assertEqual(self.stored_responses(), [])

    def test_rejects_missing_and_invalid_participant_ids(self):
        status, _, _ = self.request(
            "POST", self.response_path, body={"text": "A thought"}
        )
        self.assertEqual(status, 422)

        status, _, _ = self.request(
            "POST",
            self.response_path,
            {"x-participant-id": "not-a-uuid"},
            {"text": "A thought"},
        )
        self.assertEqual(status, 422)
        self.assertEqual(self.stored_responses(), [])

    def test_rejects_closed_and_wrong_type_questions(self):
        conn = sqlite3.connect(db.db_path())
        try:
            conn.execute(
                "UPDATE questions SET is_open = 0 WHERE id = ?",
                (self.question_id,),
            )
            conn.commit()
        finally:
            conn.close()

        status, _, _ = self.request(
            "POST", self.response_path, self.participant, {"text": "Closed"}
        )
        self.assertEqual(status, 403)

        status, body, _ = self.request(
            "POST",
            f"{self.session_path}/questions",
            self.host,
            {
                "type": "multiple_choice",
                "text": "Pick one?",
                "options": ["Yes", "No"],
            },
        )
        self.assertEqual(status, 200)
        multiple_choice_id = json.loads(body)["id"]
        status, _, _ = self.request(
            "POST",
            f"{self.session_path}/questions/{multiple_choice_id}/responses",
            self.participant,
            {"text": "Not a vote"},
        )

        self.assertEqual(status, 422)
        self.assertEqual(self.stored_responses(), [])

    def test_rejects_questions_from_another_session(self):
        other_session = self.create_session()
        other_host = {"authorization": f"Bearer {other_session['host_key']}"}
        status, body, _ = self.request(
            "POST",
            f"/api/sessions/{other_session['code']}/questions",
            other_host,
            {"type": "word_cloud", "text": "Other question?"},
        )
        self.assertEqual(status, 200)
        other_question_id = json.loads(body)["id"]

        status, _, _ = self.request(
            "POST",
            f"{self.session_path}/questions/{other_question_id}/responses",
            self.participant,
            {"text": "Wrong session"},
        )

        self.assertEqual(status, 404)
        self.assertEqual(self.stored_responses(other_question_id), [])

    def test_responses_survive_database_reinitialization(self):
        answer = "Persistent thought"
        self.request(
            "POST", self.response_path, self.participant, {"text": answer}
        )
        db.init_db()

        self.assertEqual(
            self.stored_responses(), [(self.participant_id, answer)]
        )
