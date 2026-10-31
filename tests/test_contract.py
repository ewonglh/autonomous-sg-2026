import json
from support import ApiTestCase


class ContractTests(ApiTestCase):
    def test_healthz(self):
        status, body, _ = self.request("GET", "/healthz")
        self.assertEqual((status, json.loads(body)), (200, {"status": "ok"}))

    def test_create_session(self):
        self.assertEqual(set(self.create_session()), {"code", "host_key"})

    def test_state_shape(self):
        status, body, _ = self.request("GET", "/api/sessions/ABC123/state")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"title", "active_question"})
        question = data["active_question"]
        self.assertEqual(
            set(question), {"id", "type", "text", "options", "is_open", "results_visible"}
        )
        self.assertEqual(set(question["options"][0]), {"id", "label"})

    def test_host_routes_need_bearer_key(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        for method, path in [
            ("GET", f"/api/sessions/{session['code']}/results"),
            ("GET", f"/api/sessions/{session['code']}/export.csv"),
        ]:
            self.assertEqual(self.request(method, path)[0], 401)
            self.assertEqual(self.request(method, path, host)[0], 200)

    def test_results_shape(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        _, body, _ = self.request("GET", f"/api/sessions/{session['code']}/results", host)
        results = json.loads(body)["results"]
        self.assertEqual(set(results[0]["options"][0]), {"option_id", "label", "count"})
        self.assertEqual(set(results[1]["words"][0]), {"word", "count"})

    def test_response_needs_participant_header(self):
        path = "/api/sessions/ABC123/questions/1/responses"
        self.assertEqual(self.request("POST", path, None, {"option_id": 1})[0], 422)
        headers = {"x-participant-id": "11111111-1111-1111-1111-111111111111"}
        self.assertEqual(self.request("POST", path, headers, {"option_id": 1})[0], 200)

    def test_csv_header_columns(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        _, body, headers = self.request(
            "GET", f"/api/sessions/{session['code']}/export.csv", host
        )
        self.assertTrue(headers["content-type"].startswith("text/csv"))
        self.assertEqual(
            body.decode().strip().split(","),
            ["session_code", "question_order", "question_type", "question_text",
             "answer", "participant_id", "submitted_at_utc", "qa_upvotes"],
        )


if __name__ == "__main__":
    unittest.main()
