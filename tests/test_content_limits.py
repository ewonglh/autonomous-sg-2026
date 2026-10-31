import json

from support import ApiTestCase


class ContentLimitTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        session = self.create_session()
        self.path = f"/api/sessions/{session['code']}/questions"
        self.host = {"authorization": f"Bearer {session['host_key']}"}

    def create(self, text="Pick one?", options=("A", "B"), kind="multiple_choice"):
        return self.request(
            "POST", self.path, self.host,
            {"type": kind, "text": text, "options": list(options)},
        )[0]

    def test_question_text_limit_is_300_characters(self):
        self.assertEqual(self.create(text="x" * 300), 200)
        self.assertEqual(self.create(text="x" * 301), 422)
        self.assertEqual(self.create(text="x" * 301, options=(), kind="word_cloud"), 422)

    def test_text_length_is_counted_after_trimming(self):
        self.assertEqual(self.create(text="  " + "x" * 300 + "  "), 200)

    def test_option_count_must_be_2_to_10(self):
        self.assertEqual(self.create(options=[str(i) for i in range(10)]), 200)
        self.assertEqual(self.create(options=[str(i) for i in range(11)]), 422)
        self.assertEqual(self.create(options=["Only"]), 422)

    def test_option_length_limit_is_100_characters(self):
        self.assertEqual(self.create(options=["x" * 100, "B"]), 200)
        self.assertEqual(self.create(options=["x" * 101, "B"]), 422)

    def test_duplicate_options_ignoring_case_are_rejected(self):
        self.assertEqual(self.create(options=["Yes", "yes"]), 422)
        self.assertEqual(self.create(options=["Yes", " YES "]), 422)

    def test_surrounding_spaces_are_trimmed_before_saving(self):
        status, raw, _ = self.request(
            "POST", self.path, self.host,
            {"type": "multiple_choice", "text": "  Hi?  ", "options": [" A ", " B"]},
        )
        self.assertEqual(status, 200)
        session_code = self.path.split("/")[3]
        self.request("POST", f"/api/sessions/{session_code}/active", self.host,
                     {"question_id": json.loads(raw)["id"]})
        _, state, _ = self.request("GET", f"/api/sessions/{session_code}/state")
        question = json.loads(state)["active_question"]
        self.assertEqual(question["text"], "Hi?")
        self.assertEqual([o["label"] for o in question["options"]], ["A", "B"])
