import json

from src import db
from support import ApiTestCase


class ContractTests(ApiTestCase):
    def test_healthz(self):
        status, body, _ = self.request("GET", "/healthz")
        self.assertEqual((status, json.loads(body)), (200, {"status": "ok"}))

    def test_create_session(self):
        self.assertEqual(set(self.create_session()), {"code", "host_key"})

    def test_state_shape(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        _, question_body, _ = self.request(
            "POST",
            f"/api/sessions/{session['code']}/questions",
            host,
            {"type": "multiple_choice", "text": "Pick one?", "options": ["Yes", "No"]},
        )
        question_id = json.loads(question_body)["id"]
        self.request(
            "POST", f"/api/sessions/{session['code']}/active", host,
            {"question_id": question_id},
        )

        status, body, _ = self.request("GET", f"/api/sessions/{session['code']}/state")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"title", "active_question"})
        question = data["active_question"]
        self.assertEqual(
            set(question),
            {"id", "type", "text", "options", "is_open", "results_visible", "chart"},
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
        path = f"/api/sessions/{session['code']}"
        for question in [
            {"type": "multiple_choice", "text": "Pick one?", "options": ["Yes", "No"]},
            {"type": "word_cloud", "text": "Your thoughts?"},
        ]:
            status, _, _ = self.request("POST", f"{path}/questions", host, question)
            self.assertEqual(status, 200)

        _, body, _ = self.request("GET", f"{path}/results", host)
        results = json.loads(body)["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(set(results[0]["options"][0]), {"option_id", "label", "count"})
        self.assertEqual(results[1]["words"], [])

    def test_response_needs_participant_header(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        status, body, _ = self.request(
            "POST",
            f"/api/sessions/{session['code']}/questions",
            host,
            {
                "type": "multiple_choice",
                "text": "Pick one?",
                "options": ["Yes", "No"],
            },
        )
        self.assertEqual(status, 200)
        question_id = json.loads(body)["id"]
        conn = db.connect()
        try:
            option_id = conn.execute(
                "SELECT id FROM options WHERE question_id = ? ORDER BY position LIMIT 1",
                (question_id,),
            ).fetchone()["id"]
        finally:
            conn.close()

        path = f"/api/sessions/{session['code']}/questions/{question_id}/responses"
        self.assertEqual(
            self.request("POST", path, None, {"option_id": option_id})[0], 422
        )
        headers = {"x-participant-id": "11111111-1111-1111-1111-111111111111"}
        self.assertEqual(
            self.request("POST", path, headers, {"option_id": option_id})[0], 200
        )

    def test_csv_header_columns(self):
        session = self.create_session()
        host = {"authorization": f"Bearer {session['host_key']}"}
        _, body, headers = self.request(
            "GET", f"/api/sessions/{session['code']}/export.csv", host
        )
        self.assertTrue(headers["content-type"].startswith("text/csv"))
        self.assertEqual(
            body.decode("utf-8-sig").strip().split(","),
            ["session_code", "question_order", "question_type", "question_text",
             "answer", "participant_id", "submitted_at_utc", "qa_upvotes"],
        )


if __name__ == "__main__":
    unittest.main()
