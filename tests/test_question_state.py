import sqlite3

from src import db
from support import ApiTestCase


class QuestionStateDatabaseTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.question_id = db.create_question(
            self.session["code"], "multiple_choice", "Choose one?", ["First", "Second"]
        )

    def test_update_only_changes_supplied_flags_for_session_question(self):
        changed = db.update_question_state(
            self.session["code"], self.question_id, {"is_open": False}
        )
        changed_results = db.update_question_state(
            self.session["code"], self.question_id, {"results_visible": True}
        )
        with sqlite3.connect(db.db_path()) as conn:
            flags = conn.execute(
                "SELECT is_open, results_visible FROM questions WHERE id = ?",
                (self.question_id,),
            ).fetchone()

        self.assertTrue(changed)
        self.assertTrue(changed_results)
        self.assertEqual(flags, (0, 1))

    def test_update_rejects_question_from_another_session(self):
        other_session = self.create_session()

        changed = db.update_question_state(
            other_session["code"], self.question_id, {"is_open": False}
        )

        self.assertFalse(changed)

    def test_active_question_must_belong_to_session(self):
        other_session = self.create_session()
        other_question = db.create_question(
            other_session["code"], "word_cloud", "Your thoughts?", []
        )

        self.assertFalse(db.set_active_question(self.session["code"], other_question))
        self.assertTrue(db.set_active_question(self.session["code"], self.question_id))

    def test_session_state_has_ordered_options_and_persists(self):
        self.assertTrue(db.set_active_question(self.session["code"], self.question_id))
        with sqlite3.connect(db.db_path()) as conn:
            conn.execute(
                "UPDATE options SET position = 3 - position WHERE question_id = ?",
                (self.question_id,),
            )
        db.init_db()

        state = db.get_session_state(self.session["code"])

        self.assertEqual(
            state["active_question"]["options"],
            [
                {"id": 2, "label": "Second"},
                {"id": 1, "label": "First"},
            ],
        )
        self.assertEqual(state["active_question"]["text"], "Choose one?")

    def test_session_state_returns_no_active_question_when_unset(self):
        state = db.get_session_state(self.session["code"])

        self.assertIsNotNone(state)
        self.assertIsNone(state["active_question"])
