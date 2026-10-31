import json

from src import db
from support import ApiTestCase


PARTICIPANT_ID = "11111111-1111-1111-1111-111111111111"


class MultipleChoiceResponseTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.question_id = self.create_question(
            self.session, "multiple_choice", ["Yes", "No"]
        )
        self.option_ids = self.get_option_ids(self.question_id)

    def create_question(self, session: dict, question_type: str, options=None) -> int:
        headers = {"authorization": f"Bearer {session['host_key']}"}
        body = {"type": question_type, "text": "Pick one?"}
        if options is not None:
            body["options"] = options
        status, response, _ = self.request(
            "POST", f"/api/sessions/{session['code']}/questions", headers, body
        )
        self.assertEqual(status, 200)
        return json.loads(response)["id"]

    def get_option_ids(self, question_id: int) -> list[int]:
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT id FROM options WHERE question_id = ? ORDER BY position",
                (question_id,),
            ).fetchall()
            return [row["id"] for row in rows]
        finally:
            conn.close()

    def submit(
        self, participant_id=PARTICIPANT_ID, code=None, question_id=None, option_id=None
    ):
        code = code or self.session["code"]
        question_id = question_id or self.question_id
        headers = (
            {"x-participant-id": participant_id}
            if participant_id is not None
            else None
        )
        return self.request(
            "POST",
            f"/api/sessions/{code}/questions/{question_id}/responses",
            headers,
            {"option_id": option_id if option_id is not None else self.option_ids[0]},
        )

    def response_count(self) -> int:
        conn = db.connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        finally:
            conn.close()

    def test_valid_response_is_stored_and_survives_database_reinitialization(self):
        status, body, _ = self.submit()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertEqual(self.response_count(), 1)

        db.init_db()

        conn = db.connect()
        try:
            response = conn.execute(
                """SELECT question_id, participant_id, option_id
                   FROM responses WHERE question_id = ?""",
                (self.question_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(
            tuple(response), (self.question_id, PARTICIPANT_ID, self.option_ids[0])
        )

    def test_repeat_response_returns_conflict_and_stores_one_vote(self):
        first_status, _, _ = self.submit()
        second_status, _, _ = self.submit()

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 409)
        self.assertEqual(self.response_count(), 1)

    def test_closed_question_is_rejected_without_storing_response(self):
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE questions SET is_open = 0 WHERE id = ?", (self.question_id,)
            )
            conn.commit()
        finally:
            conn.close()

        status, _, _ = self.submit()

        self.assertEqual(status, 409)
        self.assertEqual(self.response_count(), 0)

    def test_option_from_another_question_is_rejected(self):
        other_question = self.create_question(
            self.session, "multiple_choice", ["Maybe", "Later"]
        )
        other_option = self.get_option_ids(other_question)[0]

        status, _, _ = self.submit(option_id=other_option)

        self.assertEqual(status, 422)
        self.assertEqual(self.response_count(), 0)

    def test_question_from_another_session_is_rejected(self):
        other_session = self.create_session()
        other_question = self.create_question(
            other_session, "multiple_choice", ["Yes", "No"]
        )

        status, _, _ = self.submit(
            code=self.session["code"],
            question_id=other_question,
            option_id=self.get_option_ids(other_question)[0],
        )

        self.assertEqual(status, 404)
        self.assertEqual(self.response_count(), 0)

    def test_word_cloud_question_is_rejected(self):
        word_cloud = self.create_question(self.session, "word_cloud")

        status, _, _ = self.submit(question_id=word_cloud)

        self.assertEqual(status, 422)
        self.assertEqual(self.response_count(), 0)

    def test_missing_or_invalid_participant_id_is_rejected(self):
        missing_status, _, _ = self.submit(participant_id=None)
        invalid_status, _, _ = self.submit(participant_id="not-a-uuid")

        self.assertEqual(missing_status, 422)
        self.assertEqual(invalid_status, 422)
        self.assertEqual(self.response_count(), 0)
