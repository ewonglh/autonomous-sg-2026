import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from support import ApiTestCase

START = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)


class TimerTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.now = START
        clock = mock.patch("src.timers.utc_now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.session = self.create_session()
        self.base = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.voter = {"x-participant-id": str(uuid.uuid4())}

    def create(self, **extra):
        body = {"type": "multiple_choice", "text": "Pick?", "options": ["A", "B"], **extra}
        status, raw, _ = self.request("POST", f"{self.base}/questions", self.host, body)
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["id"]

    def show(self, question_id):
        status, _, _ = self.request(
            "POST", f"{self.base}/active", self.host, {"question_id": question_id}
        )
        self.assertEqual(status, 200)

    def patch(self, question_id, body):
        return self.request("PATCH", f"{self.base}/questions/{question_id}", self.host, body)[0]

    def state(self):
        _, raw, _ = self.request("GET", f"{self.base}/state")
        return json.loads(raw)["active_question"]

    def vote(self, question_id):
        _, raw, _ = self.request("GET", f"{self.base}/state")
        option_id = json.loads(raw)["active_question"]["options"][0]["id"]
        status, _, _ = self.request(
            "POST", f"{self.base}/questions/{question_id}/responses", self.voter,
            {"option_id": option_id},
        )
        return status

    def wait(self, seconds):
        self.now += timedelta(seconds=seconds)

    def test_showing_timed_slide_opens_it_and_counts_down(self):
        question_id = self.create(time_limit=15)
        self.patch(question_id, {"is_open": False, "results_visible": True})
        self.show(question_id)
        state = self.state()
        self.assertEqual(
            (state["is_open"], state["results_visible"], state["time_limit"], state["seconds_left"]),
            (True, False, 15, 15),
        )
        self.wait(4.5)
        self.assertEqual(self.state()["seconds_left"], 11)

    def test_at_zero_voting_closes_and_results_show(self):
        question_id = self.create(time_limit=15)
        self.show(question_id)
        self.wait(15)
        with mock.patch("src.routes.publish_event", new=mock.AsyncMock()) as publish:
            state = self.state()
        self.assertEqual(
            (state["is_open"], state["results_visible"], state["seconds_left"]),
            (False, True, None),
        )
        self.assertIsNotNone(state["results"])
        publish.assert_awaited_once_with(self.session["code"], "question_changed")

    def test_vote_after_time_is_up_is_rejected(self):
        question_id = self.create(time_limit=15)
        self.show(question_id)
        self.wait(16)
        self.assertEqual(self.vote(question_id), 403)

    def test_show_again_restarts_timer(self):
        question_id = self.create(time_limit=15)
        self.show(question_id)
        self.wait(20)
        self.assertFalse(self.state()["is_open"])
        self.show(question_id)
        state = self.state()
        self.assertEqual((state["is_open"], state["seconds_left"]), (True, 15))
        self.assertEqual(self.vote(question_id), 200)

    def test_patch_open_restarts_and_closed_stops(self):
        question_id = self.create(time_limit=30)
        self.show(question_id)
        self.wait(10)
        self.assertEqual(self.patch(question_id, {"is_open": False}), 200)
        self.assertIsNone(self.state()["seconds_left"])
        self.wait(60)
        self.assertFalse(self.state()["results_visible"])  # stopped, so no reveal at zero
        self.assertEqual(self.patch(question_id, {"is_open": True}), 200)
        self.assertEqual(self.state()["seconds_left"], 30)

    def test_untimed_slide_behaves_as_before(self):
        question_id = self.create()
        self.patch(question_id, {"results_visible": True})
        self.show(question_id)
        self.wait(3600)
        state = self.state()
        self.assertEqual(
            (state["is_open"], state["results_visible"], state["time_limit"], state["seconds_left"]),
            (True, True, None, None),
        )

    def test_time_limit_can_be_changed_and_removed(self):
        question_id = self.create(time_limit=15)
        self.assertEqual(self.patch(question_id, {"time_limit": 60}), 200)
        _, raw, _ = self.request("GET", f"{self.base}/questions", self.host)
        self.assertEqual(json.loads(raw)["questions"][0]["time_limit"], 60)
        self.assertEqual(self.patch(question_id, {"time_limit": None}), 200)
        self.show(question_id)
        self.assertIsNone(self.state()["time_limit"])

    def test_time_limit_range(self):
        for bad in (4, 3601, "soon"):
            status, _, _ = self.request(
                "POST", f"{self.base}/questions", self.host,
                {"type": "word_cloud", "text": "W?", "time_limit": bad},
            )
            self.assertEqual(status, 422, bad)
        question_id = self.create(time_limit=5)
        self.assertEqual(self.patch(question_id, {"time_limit": 3601}), 422)

    def test_qa_slide_stops_taking_questions_at_zero(self):
        status, raw, _ = self.request(
            "POST", f"{self.base}/questions", self.host,
            {"type": "qa", "text": "Ask", "time_limit": 30},
        )
        question_id = json.loads(raw)["id"]
        self.show(question_id)
        qa_path = f"{self.base}/questions/{question_id}/qa"
        self.assertEqual(self.request("POST", qa_path, self.voter, {"text": "Early"})[0], 200)
        self.wait(30)
        self.assertEqual(self.request("POST", qa_path, self.voter, {"text": "Late"})[0], 400)
        self.assertFalse(self.state()["results_visible"])

    def test_question_list_shows_seconds_left(self):
        timed, untimed = self.create(time_limit=60), self.create()
        self.show(timed)
        self.wait(1)
        _, raw, _ = self.request("GET", f"{self.base}/questions", self.host)
        left = {q["id"]: q["seconds_left"] for q in json.loads(raw)["questions"]}
        self.assertEqual(left, {timed: 59, untimed: None})
