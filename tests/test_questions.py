import json
import sqlite3

from src import db
from support import ApiTestCase


class QuestionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.path = f"/api/sessions/{self.session['code']}/questions"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}

    def test_create_multiple_choice_keeps_option_order(self):
        status, body, _ = self.request(
            "POST", self.path, self.host,
            {"type": "multiple_choice", "text": "  Pick one?  ", "options": [" First ", "Second"]},
        )
        question_id = json.loads(body)["id"]
        with sqlite3.connect(db.db_path()) as conn:
            question = conn.execute(
                "SELECT type, text FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            options = conn.execute(
                "SELECT label FROM options WHERE question_id = ? ORDER BY position",
                (question_id,),
            ).fetchall()

        self.assertEqual(status, 200)
        self.assertEqual(question, ("multiple_choice", "Pick one?"))
        self.assertEqual(options, [("First",), ("Second",)])

    def test_create_word_cloud_stores_no_options(self):
        status, body, _ = self.request(
            "POST", self.path, self.host,
            {"type": "word_cloud", "text": "Your thoughts?"},
        )
        question_id = json.loads(body)["id"]
        with sqlite3.connect(db.db_path()) as conn:
            question_type = conn.execute(
                "SELECT type FROM questions WHERE id = ?", (question_id,)
            ).fetchone()[0]
            option_count = conn.execute(
                "SELECT COUNT(*) FROM options WHERE question_id = ?", (question_id,)
            ).fetchone()[0]

        self.assertEqual(status, 200)
        self.assertEqual(question_type, "word_cloud")
        self.assertEqual(option_count, 0)

    def test_questions_are_ordered_and_bound_to_their_session(self):
        other_session = self.create_session()
        self.request(
            "POST", self.path, self.host,
            {"type": "word_cloud", "text": "First?"},
        )
        self.request(
            "POST", self.path, self.host,
            {"type": "word_cloud", "text": "Second?"},
        )
        other_host = {"authorization": f"Bearer {other_session['host_key']}"}
        self.request(
            "POST", f"/api/sessions/{other_session['code']}/questions", other_host,
            {"type": "word_cloud", "text": "Other?"},
        )
        with sqlite3.connect(db.db_path()) as conn:
            rows = conn.execute(
                """SELECT sessions.code, questions.position, questions.text
                   FROM questions JOIN sessions ON sessions.id = questions.session_id
                   ORDER BY sessions.code, questions.position"""
            ).fetchall()

        self.assertCountEqual(
            rows,
            [
                (self.session["code"], 1, "First?"),
                (self.session["code"], 2, "Second?"),
                (other_session["code"], 1, "Other?"),
            ],
        )

    def test_invalid_question_data_is_rejected_without_writes(self):
        invalid_bodies = [
            {"type": "multiple_choice", "text": "   ", "options": ["Yes", "No"]},
            {"type": "multiple_choice", "text": "Pick?", "options": ["Only one"]},
            {"type": "multiple_choice", "text": "Pick?", "options": ["Yes", "   "]},
            {"type": "word_cloud", "text": "Thoughts?", "options": ["Not allowed"]},
            {"type": "other", "text": "Pick?", "options": []},
        ]
        for body in invalid_bodies:
            self.assertEqual(self.request("POST", self.path, self.host, body)[0], 422)

        with sqlite3.connect(db.db_path()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM options").fetchone()[0], 0)

    def test_create_requires_valid_host_key_and_existing_session(self):
        body = {"type": "word_cloud", "text": "Thoughts?"}
        self.assertEqual(self.request("POST", self.path, body=body)[0], 401)
        self.assertEqual(
            self.request("POST", self.path, {"authorization": "Bearer wrong"}, body)[0], 401
        )
        self.assertEqual(
            self.request(
                "POST", "/api/sessions/UNKNOWN/questions", self.host, body
            )[0],
            401,
        )

    def test_questions_and_options_survive_database_reinitialization(self):
        _, body, _ = self.request(
            "POST", self.path, self.host,
            {"type": "multiple_choice", "text": "Persist?", "options": ["Yes", "No"]},
        )
        question_id = json.loads(body)["id"]
        db.init_db()

        with sqlite3.connect(db.db_path()) as conn:
            question = conn.execute(
                "SELECT text FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            options = conn.execute(
                "SELECT label FROM options WHERE question_id = ? ORDER BY position",
                (question_id,),
            ).fetchall()

        self.assertEqual(question, ("Persist?",))
        self.assertEqual(options, [("Yes",), ("No",)])
