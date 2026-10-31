import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src import db
from src.db import SESSION_IDLE_TIMEOUT, has_session_expired
from support import ApiTestCase


class SessionExpiryTimeTests(unittest.TestCase):
    def test_session_is_active_just_before_timeout(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        last_active_at = (now - SESSION_IDLE_TIMEOUT + timedelta(microseconds=1)).isoformat()

        self.assertFalse(has_session_expired(last_active_at, now))

    def test_session_expires_at_timeout(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        last_active_at = (now - SESSION_IDLE_TIMEOUT).isoformat()

        self.assertTrue(has_session_expired(last_active_at, now))

    def test_session_remains_expired_after_timeout(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        last_active_at = (now - SESSION_IDLE_TIMEOUT - timedelta(seconds=1)).isoformat()

        self.assertTrue(has_session_expired(last_active_at, now))

    def test_utc_z_timestamp_is_supported(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        last_active_at = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        self.assertFalse(has_session_expired(last_active_at, now))


class SessionExpiryRouteTests(ApiTestCase):
    NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
    PARTICIPANT_ID = "11111111-1111-1111-1111-111111111111"

    def setUp(self):
        super().setUp()
        self.clock = patch("src.db.utc_now", return_value=self.NOW)
        self.mock_clock = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}

    def set_last_active(self, last_active_at: datetime) -> None:
        conn = sqlite3.connect(db.db_path())
        try:
            conn.execute(
                "UPDATE sessions SET last_active_at = ? WHERE code = ?",
                (last_active_at.isoformat(), self.code),
            )
            conn.commit()
        finally:
            conn.close()

    def get_last_active(self) -> str:
        conn = sqlite3.connect(db.db_path())
        try:
            return conn.execute(
                "SELECT last_active_at FROM sessions WHERE code = ?", (self.code,)
            ).fetchone()[0]
        finally:
            conn.close()

    def create_question(self) -> int:
        status, body, _ = self.request(
            "POST",
            f"/api/sessions/{self.code}/questions",
            self.host,
            {"type": "multiple_choice", "text": "Pick one?", "options": ["Yes", "No"]},
        )
        self.assertEqual(status, 200)
        return json.loads(body)["id"]

    def option_id(self, question_id: int) -> int:
        conn = sqlite3.connect(db.db_path())
        try:
            return conn.execute(
                "SELECT id FROM options WHERE question_id = ? ORDER BY position LIMIT 1",
                (question_id,),
            ).fetchone()[0]
        finally:
            conn.close()

    def row_counts(self) -> tuple[int, int]:
        conn = sqlite3.connect(db.db_path())
        try:
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            responses = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
            return sessions, responses
        finally:
            conn.close()

    def submit_response(self, question_id: int, option_id: int) -> int:
        headers = {"x-participant-id": self.PARTICIPANT_ID}
        status, _, _ = self.request(
            "POST",
            f"/api/sessions/{self.code}/questions/{question_id}/responses",
            headers,
            {"option_id": option_id},
        )
        return status

    def test_expired_session_returns_404_for_all_session_api_routes(self):
        question_id = self.create_question()
        option_id = self.option_id(question_id)
        self.assertEqual(self.submit_response(question_id, option_id), 200)
        self.set_last_active(self.NOW - SESSION_IDLE_TIMEOUT)
        expired_timestamp = self.get_last_active()
        initial_counts = self.row_counts()
        response_path = (
            f"/api/sessions/{self.code}/questions/{question_id}/responses"
        )
        requests = [
            ("GET", f"/api/sessions/{self.code}/state", None, None),
            (
                "POST",
                f"/api/sessions/{self.code}/questions",
                self.host,
                {"type": "word_cloud", "text": "Another question?"},
            ),
            (
                "PATCH",
                f"/api/sessions/{self.code}/questions/{question_id}",
                self.host,
                {"is_open": False},
            ),
            (
                "POST",
                f"/api/sessions/{self.code}/active",
                self.host,
                {"question_id": question_id},
            ),
            (
                "POST",
                response_path,
                {"x-participant-id": self.PARTICIPANT_ID},
                {"option_id": option_id},
            ),
            ("GET", f"/api/sessions/{self.code}/results", self.host, None),
            ("GET", f"/api/sessions/{self.code}/export.csv", self.host, None),
        ]

        for method, path, headers, body in requests:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path, headers, body)[0], 404)

        self.assertEqual(self.get_last_active(), expired_timestamp)
        self.assertEqual(self.row_counts(), initial_counts)

    def test_expired_host_request_returns_404_before_authentication(self):
        self.set_last_active(self.NOW - SESSION_IDLE_TIMEOUT)

        status, _, _ = self.request(
            "GET", f"/api/sessions/{self.code}/results", {"authorization": "Bearer wrong"}
        )

        self.assertEqual(status, 404)
        self.assertEqual(
            self.get_last_active(), (self.NOW - SESSION_IDLE_TIMEOUT).isoformat()
        )

    def test_successful_host_activity_refreshes_session(self):
        self.set_last_active(self.NOW - timedelta(hours=23))

        status, _, _ = self.request(
            "POST",
            f"/api/sessions/{self.code}/questions",
            self.host,
            {"type": "word_cloud", "text": "Your thoughts?"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(self.get_last_active(), self.NOW.isoformat())

    def test_successful_participant_activity_extends_expiry(self):
        self.set_last_active(self.NOW - timedelta(hours=23))
        self.assertEqual(
            self.request("GET", f"/api/sessions/{self.code}/state")[0], 200
        )
        self.assertEqual(self.get_last_active(), self.NOW.isoformat())

        self.mock_clock.return_value = self.NOW + timedelta(hours=2)
        self.assertEqual(
            self.request("GET", f"/api/sessions/{self.code}/state")[0], 200
        )
        self.assertEqual(
            self.get_last_active(), (self.NOW + timedelta(hours=2)).isoformat()
        )

        self.mock_clock.return_value = self.NOW + timedelta(hours=26)
        self.assertEqual(
            self.request("GET", f"/api/sessions/{self.code}/state")[0], 404
        )

    def test_unauthenticated_host_request_does_not_refresh_session(self):
        last_active = self.NOW - timedelta(hours=1)
        self.set_last_active(last_active)

        status, _, _ = self.request(
            "POST",
            f"/api/sessions/{self.code}/questions",
            {"authorization": "Bearer wrong"},
            {"type": "word_cloud", "text": "Your thoughts?"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(self.get_last_active(), last_active.isoformat())

    def test_rejected_participant_response_does_not_refresh_session(self):
        question_id = self.create_question()
        option_id = self.option_id(question_id)
        self.assertEqual(self.submit_response(question_id, option_id), 200)
        last_active = self.NOW - timedelta(hours=1)
        self.set_last_active(last_active)

        self.assertEqual(self.submit_response(question_id, option_id), 409)
        self.assertEqual(self.get_last_active(), last_active.isoformat())
