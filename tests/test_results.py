import json
import sqlite3

from src import db
from support import ApiTestCase


class SessionResultsDatabaseTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()

    def add_response(self, question_id, participant_id, *, option_id=None, text=None, created_at):
        conn = db.connect()
        try:
            conn.execute(
                """INSERT INTO responses
                   (question_id, participant_id, option_id, text, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (question_id, participant_id, option_id, text, created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def test_returns_empty_list_when_session_has_no_questions(self):
        self.assertEqual(db.get_session_results(self.session["code"]), [])

    def test_choice_results_include_every_option_and_zero_counts(self):
        question_id = db.create_question(
            self.session["code"], "multiple_choice", "Pick one?", ["Yes", "No", "Maybe"]
        )
        conn = sqlite3.connect(db.db_path())
        try:
            option_ids = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM options WHERE question_id = ? ORDER BY position",
                    (question_id,),
                )
            ]
        finally:
            conn.close()
        self.add_response(
            question_id, "participant-1", option_id=option_ids[0],
            created_at="2026-10-31T00:00:00+00:00",
        )

        self.assertEqual(
            db.get_session_results(self.session["code"]),
            [
                {
                    "question_id": question_id,
                    "type": "multiple_choice",
                    "options": [
                        {"option_id": option_ids[0], "label": "Yes", "count": 1},
                        {"option_id": option_ids[1], "label": "No", "count": 0},
                        {"option_id": option_ids[2], "label": "Maybe", "count": 0},
                    ],
                }
            ],
        )

    def test_word_results_trim_group_case_insensitively_and_keep_phrases(self):
        question_id = db.create_question(
            self.session["code"], "word_cloud", "Where to eat?", []
        )
        for index, (text, created_at) in enumerate(
            [
                ("  New York City  ", "2026-10-31T00:00:00+00:00"),
                ("new york city", "2026-10-31T00:01:00+00:00"),
                ("NEW YORK CITY", "2026-10-31T00:02:00+00:00"),
                ("  Good food ", "2026-10-31T00:03:00+00:00"),
            ]
        ):
            self.add_response(
                question_id, f"participant-{index}", text=text, created_at=created_at
            )

        self.assertEqual(
            db.get_session_results(self.session["code"]),
            [
                {
                    "question_id": question_id,
                    "type": "word_cloud",
                    "words": [
                        {"word": "New York City", "count": 3},
                        {"word": "Good food", "count": 1},
                    ],
                }
            ],
        )

    def test_results_cover_multiple_questions_and_survive_reinitialization(self):
        first_id = db.create_question(
            self.session["code"], "word_cloud", "First?", []
        )
        second_id = db.create_question(
            self.session["code"], "multiple_choice", "Second?", ["A", "B"]
        )
        self.add_response(
            first_id, "participant-1", text="Saved", created_at="2026-10-31T00:00:00+00:00"
        )
        self.add_response(
            second_id, "participant-2", option_id=2,
            created_at="2026-10-31T00:01:00+00:00",
        )

        db.init_db()

        results = db.get_session_results(self.session["code"])
        self.assertEqual([result["question_id"] for result in results], [first_id, second_id])
        self.assertEqual(results[0]["words"], [{"word": "Saved", "count": 1}])
        self.assertEqual(results[1]["options"][1]["count"], 1)


class SessionResultsRouteTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.session_path = f"/api/sessions/{self.code}"

    def create_question(self, question_type, text, options=None):
        body = {"type": question_type, "text": text}
        if options is not None:
            body["options"] = options
        status, response, _ = self.request(
            "POST", f"{self.session_path}/questions", self.host, body
        )
        self.assertEqual(status, 200)
        return json.loads(response)["id"]

    def option_ids(self, question_id):
        conn = db.connect()
        try:
            return [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM options WHERE question_id = ? ORDER BY position",
                    (question_id,),
                )
            ]
        finally:
            conn.close()

    def test_results_route_requires_valid_host_key(self):
        path = f"{self.session_path}/results"
        self.assertEqual(self.request("GET", path)[0], 401)
        self.assertEqual(
            self.request("GET", path, {"authorization": "Bearer wrong"})[0], 401
        )

        status, body, _ = self.request("GET", path, self.host)

        self.assertEqual((status, json.loads(body)), (200, {"results": []}))

    def test_results_route_returns_saved_choice_and_word_totals(self):
        choice_id = self.create_question(
            "multiple_choice", "Choose one?", ["Yes", "No"]
        )
        word_id = self.create_question("word_cloud", "Where?", [])
        yes_id, no_id = self.option_ids(choice_id)

        self.request(
            "POST",
            f"{self.session_path}/questions/{choice_id}/responses",
            {"x-participant-id": "11111111-1111-4111-8111-111111111111"},
            {"option_id": yes_id},
        )
        for participant_id, text in [
            ("22222222-2222-4222-8222-222222222222", "  Singapore "),
            ("33333333-3333-4333-8333-333333333333", "SINGAPORE"),
        ]:
            self.request(
                "POST",
                f"{self.session_path}/questions/{word_id}/responses",
                {"x-participant-id": participant_id},
                {"text": text},
            )

        status, body, _ = self.request(
            "GET", f"{self.session_path}/results", self.host
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {
                "results": [
                    {
                        "question_id": choice_id,
                        "type": "multiple_choice",
                        "options": [
                            {"option_id": yes_id, "label": "Yes", "count": 1},
                            {"option_id": no_id, "label": "No", "count": 0},
                        ],
                    },
                    {
                        "question_id": word_id,
                        "type": "word_cloud",
                        "words": [{"word": "Singapore", "count": 2}],
                    },
                ]
            },
        )
