import json

from src import db
from support import ApiTestCase


class QuestionListTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.path = f"/api/sessions/{self.code}/questions"

    def test_question_list_requires_host_key(self):
        self.assertEqual(self.request("GET", self.path)[0], 401)
        self.assertEqual(
            self.request("GET", self.path, {"authorization": "Bearer wrong"})[0],
            401,
        )

    def test_returns_questions_in_position_order_with_flags_and_counts(self):
        first = db.create_question(
            self.code, "multiple_choice", "First?", ["One", "Two"]
        )
        second = db.create_question(self.code, "word_cloud", "Second?", [])
        third = db.create_question(
            self.code, "multiple_choice", "Third?", ["Yes", "No"]
        )
        conn = db.connect()
        try:
            conn.execute("UPDATE questions SET position = 3 WHERE id = ?", (first,))
            conn.execute("UPDATE questions SET position = 1 WHERE id = ?", (second,))
            conn.execute("UPDATE questions SET position = 2 WHERE id = ?", (third,))
            conn.execute(
                "UPDATE options SET position = 3 - position WHERE question_id = ?",
                (first,),
            )
            conn.commit()
        finally:
            conn.close()
        db.update_question_state(
            self.code, third, {"is_open": False, "results_visible": True}
        )
        db.set_active_question(self.code, second)
        db.save_multiple_choice_response(self.code, third, "participant-one", 3)
        db.save_word_cloud_response(self.code, second, "participant-two", "A thought")

        status, body, _ = self.request("GET", self.path, self.host)
        result = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(result["active_question_id"], second)
        self.assertEqual(
            [question["id"] for question in result["questions"]],
            [second, third, first],
        )
        self.assertEqual(
            [question["position"] for question in result["questions"]], [1, 2, 3]
        )
        self.assertEqual(result["questions"][0]["response_count"], 1)
        self.assertEqual(result["questions"][1]["response_count"], 1)
        self.assertFalse(result["questions"][1]["is_open"])
        self.assertTrue(result["questions"][1]["results_visible"])
        self.assertEqual(
            result["questions"][2]["options"],
            [{"id": 2, "label": "Two"}, {"id": 1, "label": "One"}],
        )
