import unittest
from datetime import datetime, timedelta, timezone

from src.db import SESSION_IDLE_TIMEOUT, has_session_expired


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
