import json
import unittest

from src import db, routes
from src.limits import RateLimiter
from support import ApiTestCase


class ControlledClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.clock = ControlledClock()
        self.limiter = RateLimiter(clock=self.clock)

    def test_allows_requests_up_to_the_limit(self):
        self.assertIsNone(self.limiter.check_request("client", 2))
        self.assertIsNone(self.limiter.check_request("client", 2))

    def test_returns_wait_until_the_oldest_request_expires(self):
        self.limiter.check_request("client", 2)
        self.limiter.check_request("client", 2)
        self.clock.advance(10)

        self.assertEqual(self.limiter.check_request("client", 2), 50)

    def test_allows_a_request_when_the_window_expires(self):
        self.limiter.check_request("client", 1)
        self.clock.advance(60)

        self.assertIsNone(self.limiter.check_request("client", 1))

    def test_keeps_limits_separate_by_key(self):
        self.limiter.check_request("first", 1)

        self.assertIsNone(self.limiter.check_request("second", 1))


class ControlledApiTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.clock = ControlledClock()
        routes.rate_limiter = RateLimiter(clock=self.clock)


class SessionCreationRateLimitTests(ControlledApiTestCase):
    def test_allows_five_sessions_then_returns_retry_after_and_resets(self):
        for _ in range(5):
            status, _, _ = self.request("POST", "/api/sessions")
            self.assertEqual(status, 200)

        status, _, headers = self.request("POST", "/api/sessions")

        self.assertEqual(status, 429)
        self.assertEqual(headers["retry-after"], "60")

        self.clock.advance(60)
        self.assertEqual(self.request("POST", "/api/sessions")[0], 200)


class ResponseRateLimitTests(ControlledApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.code = self.session["code"]
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.word_cloud_questions = [
            self.create_question("word_cloud") for _ in range(3)
        ]
        self.multiple_choice_questions = [
            self.create_question("multiple_choice", ["Yes", "No"])
            for _ in range(2)
        ]

    def create_question(self, question_type, options=None):
        body = {"type": question_type, "text": "Your answer?"}
        if options is not None:
            body["options"] = options
        status, response, _ = self.request(
            "POST", f"/api/sessions/{self.code}/questions", self.host, body
        )
        self.assertEqual(status, 200)
        return json.loads(response)["id"]

    def submit_word_cloud(self, question_id, participant_id):
        return self.request(
            "POST",
            f"/api/sessions/{self.code}/questions/{question_id}/responses",
            {"x-participant-id": participant_id},
            {"text": "A thought"},
        )

    def submit_multiple_choice(self, question_id, participant_id):
        conn = db.connect()
        try:
            option_id = conn.execute(
                "SELECT id FROM options WHERE question_id = ? ORDER BY position LIMIT 1",
                (question_id,),
            ).fetchone()["id"]
        finally:
            conn.close()
        return self.request(
            "POST",
            f"/api/sessions/{self.code}/questions/{question_id}/responses",
            {"x-participant-id": participant_id},
            {"option_id": option_id},
        )

    def test_response_limit_is_shared_across_types_participants_and_window(self):
        participant_id = "11111111-1111-1111-1111-111111111111"
        other_participant_id = "22222222-2222-2222-2222-222222222222"

        for question_id in self.word_cloud_questions:
            for _ in range(3):
                status, _, _ = self.submit_word_cloud(question_id, participant_id)
                self.assertEqual(status, 200)

        status, _, _ = self.submit_multiple_choice(
            self.multiple_choice_questions[0], participant_id
        )
        self.assertEqual(status, 200)

        status, _, headers = self.submit_multiple_choice(
            self.multiple_choice_questions[1], participant_id
        )
        self.assertEqual(status, 429)
        self.assertEqual(headers["retry-after"], "60")

        status, _, _ = self.submit_multiple_choice(
            self.multiple_choice_questions[1], other_participant_id
        )
        self.assertEqual(status, 200)

        self.clock.advance(60)
        status, _, _ = self.submit_multiple_choice(
            self.multiple_choice_questions[1], participant_id
        )
        self.assertEqual(status, 200)
