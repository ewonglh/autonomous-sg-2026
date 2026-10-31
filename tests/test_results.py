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
