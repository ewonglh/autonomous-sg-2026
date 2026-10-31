import json

from support import ApiTestCase


class SlideTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.base = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}

    def create(self, body):
        status, raw, _ = self.request("POST", f"{self.base}/questions", self.host, body)
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["id"]

    def poll(self, **extra):
        return self.create(
            {"type": "multiple_choice", "text": "Pick?", "options": ["A", "B"], **extra}
        )

    def active_state(self, question_id):
        status, _, _ = self.request(
            "POST", f"{self.base}/active", self.host, {"question_id": question_id}
        )
        self.assertEqual(status, 200)
        _, raw, _ = self.request("GET", f"{self.base}/state")
        return json.loads(raw)["active_question"]

    def result_order(self):
        _, raw, _ = self.request("GET", f"{self.base}/results", self.host)
        return [result["question_id"] for result in json.loads(raw)["results"]]

    def test_donut_poll_shows_donut_in_state(self):
        self.assertEqual(self.active_state(self.poll(chart="donut"))["chart"], "donut")

    def test_poll_chart_defaults_to_bar(self):
        self.assertEqual(self.active_state(self.poll())["chart"], "bar")

    def test_patch_changes_chart(self):
        question_id = self.poll(chart="donut")
        status, _, _ = self.request(
            "PATCH", f"{self.base}/questions/{question_id}", self.host, {"chart": "bar"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.active_state(question_id)["chart"], "bar")

    def test_chart_rejected_for_other_types(self):
        status, _, _ = self.request(
            "POST", f"{self.base}/questions", self.host,
            {"type": "word_cloud", "text": "Word?", "chart": "donut"},
        )
        self.assertEqual(status, 422)
        cloud = self.create({"type": "word_cloud", "text": "Word?"})
        for bad in ({"chart": "donut"}, {"chart": "pie"}):
            status, _, _ = self.request(
                "PATCH", f"{self.base}/questions/{cloud}", self.host, bad
            )
            self.assertIn(status, (404, 422))

    def test_qa_slide_can_be_active(self):
        question_id = self.create({"type": "qa", "text": "Ask us anything"})
        state = self.active_state(question_id)
        self.assertEqual(state["type"], "qa")
        self.assertEqual(state["options"], [])
        self.assertIsNone(state["chart"])
        self.assertIn(question_id, self.result_order())

    def test_qa_slide_rejects_options(self):
        status, _, _ = self.request(
            "POST", f"{self.base}/questions", self.host,
            {"type": "qa", "text": "Ask", "options": ["A", "B"]},
        )
        self.assertEqual(status, 422)

    def test_order_sets_positions(self):
        first, second, third = self.poll(), self.poll(), self.poll()
        status, raw, _ = self.request(
            "PUT", f"{self.base}/questions/order", self.host,
            {"question_ids": [third, first, second]},
        )
        self.assertEqual((status, json.loads(raw)), (200, {"ok": True}))
        self.assertEqual(self.result_order(), [third, first, second])
        fourth = self.poll()
        self.assertEqual(self.result_order(), [third, first, second, fourth])

    def test_order_must_match_session_questions(self):
        first, second = self.poll(), self.poll()
        for ids in ([first], [first, first], [first, second, 999]):
            status, _, _ = self.request(
                "PUT", f"{self.base}/questions/order", self.host, {"question_ids": ids}
            )
            self.assertEqual(status, 422, ids)
        self.assertEqual(self.result_order(), [first, second])

    def test_order_requires_host_key(self):
        status, _, _ = self.request(
            "PUT", f"{self.base}/questions/order", None, {"question_ids": []}
        )
        self.assertEqual(status, 401)
