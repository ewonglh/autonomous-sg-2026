import hashlib
import json
import os
import sqlite3

from src import db
from src.auth import hash_host_key
from support import ApiTestCase


class SessionTests(ApiTestCase):
    def test_create_returns_unique_code_and_random_host_key(self):
        first = self.create_session()
        second = self.create_session()

        self.assertNotEqual(first["code"], second["code"])
        self.assertNotEqual(first["host_key"], second["host_key"])
        self.assertGreaterEqual(len(first["host_key"]), 40)

    def test_session_title_defaults_and_can_be_set(self):
        default_session = self.create_session()
        status, body, _ = self.request(
            "GET", f"/api/sessions/{default_session['code']}/state"
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["title"], "Untitled session")

        status, body, _ = self.request(
            "POST", "/api/sessions", body={"title": "Welcome"}
        )
        self.assertEqual(status, 200)
        session = json.loads(body)
        _, state_body, _ = self.request(
            "GET", f"/api/sessions/{session['code']}/state"
        )
        self.assertEqual(json.loads(state_body)["title"], "Welcome")

    def test_session_title_limit_is_enforced(self):
        status, _, _ = self.request(
            "POST", "/api/sessions", body={"title": "x" * 121}
        )
        self.assertEqual(status, 422)

    def test_only_host_key_hash_is_stored(self):
        session = self.create_session()
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            stored_hash = conn.execute(
                "SELECT host_key_hash FROM sessions WHERE code = ?", (session["code"],)
            ).fetchone()[0]

        self.assertEqual(stored_hash, hash_host_key(session["host_key"]))
        self.assertNotEqual(stored_hash, session["host_key"])
        self.assertEqual(len(stored_hash), hashlib.sha256().digest_size * 2)

    def test_host_auth_rejects_missing_wrong_and_unknown_session_keys(self):
        session = self.create_session()
        path = f"/api/sessions/{session['code']}/questions"
        body = {"type": "word_cloud", "text": "Your thoughts?"}

        self.assertEqual(self.request("POST", path, body=body)[0], 401)
        self.assertEqual(
            self.request("POST", path, {"authorization": "Bearer wrong"}, body)[0], 401
        )
        self.assertEqual(
            self.request(
                "POST", "/api/sessions/UNKNOWN/questions",
                {"authorization": "Bearer any-key"}, body,
            )[0],
            401,
        )

    def test_shared_host_auth_protects_all_host_routes(self):
        session = self.create_session()
        code = session["code"]
        key = {"authorization": f"Bearer {session['host_key']}"}
        routes = [
            ("POST", f"/api/sessions/{code}/questions", {"type": "word_cloud", "text": "Q?"}),
            ("PATCH", f"/api/sessions/{code}/questions/1", {}),
            ("POST", f"/api/sessions/{code}/active", {"question_id": 1}),
            ("GET", f"/api/sessions/{code}/results", None),
            ("GET", f"/api/sessions/{code}/export.csv", None),
        ]
        for method, path, body in routes:
            self.assertEqual(self.request(method, path)[0], 401)
            self.assertEqual(
                self.request(method, path, {"authorization": "Bearer wrong"}, body)[0], 401
            )
            self.assertEqual(self.request(method, path, key, body)[0], 200)

    def test_session_auth_survives_database_reinitialization(self):
        session = self.create_session()
        db.init_db()
        path = f"/api/sessions/{session['code']}/questions"

        status, _, _ = self.request(
            "POST", path,
            {"authorization": f"Bearer {session['host_key']}"},
            {"type": "word_cloud", "text": "Still here?"},
        )

        self.assertEqual(status, 200)

    def test_every_connection_enables_foreign_keys(self):
        first = db.connect()
        second = db.connect()
        try:
            self.assertEqual(first.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(second.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            first.close()
            second.close()
