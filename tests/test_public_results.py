import json

from src import db
from support import ApiTestCase


class PublicResultsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.base = f"/api/sessions/{self.code}"

    def test_state_hides_results_until_the_host_reveals_them(self):
        question_id = db.create_question(
            self.code, "multiple_choice", "Pick one?", ["Yes", "No"]
        )
        conn = db.connect()
        try:
            option_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM options WHERE question_id = ? ORDER BY position",
                    (question_id,),
                )
            ]
        finally:
            conn.close()
        option_id, second_option_id = option_ids
        db.set_active_question(self.code, question_id)
        db.save_multiple_choice_response(
            self.code, question_id, "participant-one", option_id
        )
        path = f"{self.base}/state"

        status, body, _ = self.request("GET", path)
        active = json.loads(body)["active_question"]
        self.assertEqual(status, 200)
        self.assertEqual(active["response_count"], 1)
        self.assertIsNone(active["results"])

        self.request(
            "PATCH",
            f"{self.base}/questions/{question_id}",
            self.host,
            {"results_visible": True},
        )
        status, body, _ = self.request("GET", path)
        active = json.loads(body)["active_question"]

        self.assertEqual(status, 200)
        self.assertEqual(
            active["results"],
            {
                "options": [
                    {"option_id": option_id, "label": "Yes", "count": 1},
                    {"option_id": second_option_id, "label": "No", "count": 0},
                ]
            },
        )

    def test_revealed_word_cloud_uses_shared_result_counts(self):
        question_id = db.create_question(self.code, "word_cloud", "Where?", [])
        db.set_active_question(self.code, question_id)
        db.save_word_cloud_response(
            self.code, question_id, "participant-one", "New York City"
        )
        db.save_word_cloud_response(
            self.code, question_id, "participant-two", "new york city"
        )
        db.update_question_state(self.code, question_id, {"results_visible": True})

        status, body, _ = self.request("GET", f"{self.base}/state")
        active = json.loads(body)["active_question"]

        self.assertEqual(status, 200)
        self.assertEqual(active["response_count"], 2)
        self.assertEqual(
            active["results"],
            {"words": [{"word": "New York City", "count": 2}]},
        )
