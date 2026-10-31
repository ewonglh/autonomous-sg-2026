import json
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


class QuestionStateRouteTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}

    def create_question(self, text="Choose one?", options=None):
        body = {"type": "multiple_choice", "text": text, "options": options or ["First", "Second"]}
        status, response, _ = self.request(
            "POST", f"/api/sessions/{self.code}/questions", self.host, body
        )
        self.assertEqual(status, 200)
        return json.loads(response)["id"]

    def test_patch_updates_only_supplied_flags_and_returns_ok(self):
        question_id = self.create_question()
        path = f"/api/sessions/{self.code}/questions/{question_id}"
        self.assertTrue(db.set_active_question(self.code, question_id))

        status, body, _ = self.request("PATCH", path, self.host, {"is_open": False})
        self.assertEqual((status, json.loads(body)), (200, {"ok": True}))
        self.request("PATCH", path, self.host, {"results_visible": True})

        _, state_body, _ = self.request("GET", f"/api/sessions/{self.code}/state")
        active = json.loads(state_body)["active_question"]

        self.assertFalse(active["is_open"])
        self.assertTrue(active["results_visible"])
        self.request("PATCH", path, self.host, {"is_open": True})
        _, state_body, _ = self.request("GET", f"/api/sessions/{self.code}/state")
        self.assertTrue(json.loads(state_body)["active_question"]["is_open"])

    def test_patch_requires_host_key_and_rejects_null_flags(self):
        question_id = self.create_question()
        path = f"/api/sessions/{self.code}/questions/{question_id}"

        self.assertEqual(self.request("PATCH", path, body={"is_open": False})[0], 401)
        self.assertEqual(
            self.request(
                "PATCH", path, {"authorization": "Bearer wrong"}, {"is_open": False}
            )[0],
            401,
        )
        self.assertEqual(self.request("PATCH", path, self.host, {})[0], 200)
        self.assertEqual(self.request("PATCH", path, self.host, {"is_open": None})[0], 422)

    def test_active_question_requires_host_key_and_owns_question(self):
        question_id = self.create_question()
        path = f"/api/sessions/{self.code}/active"
        body = {"question_id": question_id}

        self.assertEqual(self.request("POST", path, body=body)[0], 401)
        self.assertEqual(
            self.request("POST", path, {"authorization": "Bearer wrong"}, body)[0], 401
        )
        status, response, _ = self.request("POST", path, self.host, body)
        self.assertEqual((status, json.loads(response)), (200, {"ok": True}))

    def test_public_state_returns_active_question_with_ordered_options(self):
        question_id = self.create_question()
        with sqlite3.connect(db.db_path()) as conn:
            conn.execute(
                "UPDATE options SET position = 3 - position WHERE question_id = ?",
                (question_id,),
            )
        self.request(
            "PATCH", f"/api/sessions/{self.code}/questions/{question_id}",
            self.host, {"is_open": False, "results_visible": True},
        )
        self.request(
            "POST", f"/api/sessions/{self.code}/active", self.host,
            {"question_id": question_id},
        )

        status, body, _ = self.request("GET", f"/api/sessions/{self.code}/state")
        state = json.loads(body)
        active = state["active_question"]

        self.assertEqual(status, 200)
        self.assertEqual(active["id"], question_id)
        self.assertEqual(active["type"], "multiple_choice")
        self.assertEqual(
            active["options"],
            [{"id": 2, "label": "Second"}, {"id": 1, "label": "First"}],
        )
        self.assertFalse(active["is_open"])
        self.assertTrue(active["results_visible"])

    def test_public_state_is_null_without_active_question_and_persists(self):
        path = f"/api/sessions/{self.code}/state"
        status, body, _ = self.request("GET", path)
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)["active_question"])

        question_id = self.create_question()
        self.request(
            "POST", f"/api/sessions/{self.code}/active", self.host,
            {"question_id": question_id},
        )
        db.init_db()

        _, body, _ = self.request("GET", path)
        self.assertEqual(json.loads(body)["active_question"]["id"], question_id)

    def test_host_routes_reject_question_from_another_session(self):
        self.create_question()
        other_session = self.create_session()
        other_question = db.create_question(
            other_session["code"], "word_cloud", "Your thoughts?", []
        )

        active_status = self.request(
            "POST", f"/api/sessions/{self.code}/active", self.host,
            {"question_id": other_question},
        )[0]
        patch_status = self.request(
            "PATCH", f"/api/sessions/{self.code}/questions/{other_question}",
            self.host, {"is_open": False},
        )[0]

        self.assertEqual(active_status, 404)
        self.assertEqual(patch_status, 404)
        self.assertIsNone(db.get_session_state(self.code)["active_question"])
