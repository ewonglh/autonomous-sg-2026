import base64
import json
from unittest import mock

from support import ApiTestCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def data_url(data: bytes, media_type: str = "image/png") -> str:
    return f"data:{media_type};base64,{base64.b64encode(data).decode()}"


class ImageTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.create_session()
        self.base = f"/api/sessions/{self.session['code']}"
        self.host = {"authorization": f"Bearer {self.session['host_key']}"}
        self.first = self.create()
        self.second = self.create()

    def create(self):
        status, raw, _ = self.request(
            "POST", f"{self.base}/questions", self.host, {"type": "word_cloud", "text": "W?"}
        )
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["id"]

    def put(self, qid, url, headers=None):
        return self.request(
            "PUT", f"{self.base}/questions/{qid}/image",
            self.host if headers is None else headers, {"data_url": url},
        )[0]

    def delete(self, qid, headers=None):
        return self.request(
            "DELETE", f"{self.base}/questions/{qid}/image",
            self.host if headers is None else headers,
        )[0]

    def active_image_url(self, qid):
        self.request("POST", f"{self.base}/active", self.host, {"question_id": qid})
        _, raw, _ = self.request("GET", f"{self.base}/state")  # no host key: any device
        return json.loads(raw)["active_question"]["image_url"]

    def fetch(self, url):
        path = url.split("?")[0]
        return self.request("GET", path)

    def test_uploaded_picture_shows_in_state_and_is_served(self):
        self.assertEqual(self.put(self.first, data_url(PNG)), 200)
        url = self.active_image_url(self.first)
        self.assertIsNotNone(url)
        status, body, headers = self.fetch(url)
        self.assertEqual((status, body, headers["content-type"]), (200, PNG, "image/png"))
        self.assertEqual(headers["x-content-type-options"], "nosniff")

    def test_delete_clears_picture(self):
        self.put(self.first, data_url(PNG))
        self.assertEqual(self.delete(self.first), 200)
        self.assertIsNone(self.active_image_url(self.first))
        self.assertEqual(self.delete(self.first), 200)  # deleting twice is fine

    def test_slides_keep_separate_pictures(self):
        self.put(self.first, data_url(PNG))
        self.put(self.second, data_url(JPEG, "image/jpeg"))
        self.assertEqual(self.fetch(self.active_image_url(self.first))[1], PNG)
        self.assertEqual(self.fetch(self.active_image_url(self.second))[1], JPEG)
        _, raw, _ = self.request("GET", f"{self.base}/questions", self.host)
        urls = [q["image_url"] for q in json.loads(raw)["questions"]]
        self.assertTrue(all(urls) and urls[0] != urls[1])

    def test_replacing_picture_changes_url(self):
        self.put(self.first, data_url(PNG))
        before = self.active_image_url(self.first)
        self.put(self.first, data_url(JPEG, "image/jpeg"))
        self.assertNotEqual(self.active_image_url(self.first), before)

    def test_rejects_non_images(self):
        bad = [
            "not a data url",
            data_url(b"<svg onload=alert(1)>", "image/svg+xml"),
            data_url(b"hello world", "image/png"),  # label says PNG, bytes do not
            "data:image/png;base64,@@@not-base64@@@",
            data_url(PNG, "text/html"),
        ]
        for url in bad:
            self.assertEqual(self.put(self.first, url), 422, url[:40])
        self.assertIsNone(self.active_image_url(self.first))

    def test_rejects_oversize_upload(self):
        big = data_url(PNG + b"\x00" * 1_200_000)
        self.assertGreater(len(big), 1_500_000)
        self.assertEqual(self.put(self.first, big), 413)

    def test_host_routes_need_key(self):
        self.assertEqual(self.put(self.first, data_url(PNG), {}), 401)
        self.assertEqual(self.delete(self.first, {}), 401)

    def test_unknown_slide_is_404(self):
        self.assertEqual(self.put(999, data_url(PNG)), 404)
        other = self.create_session()
        status, _, _ = self.request(
            "PUT", f"/api/sessions/{other['code']}/questions/{self.first}/image",
            {"authorization": f"Bearer {other['host_key']}"}, {"data_url": data_url(PNG)},
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.request("GET", f"{self.base}/questions/{self.first}/image")[0], 404)

    def test_deleting_slide_removes_picture(self):
        self.put(self.first, data_url(PNG))
        status, _, _ = self.request("DELETE", f"{self.base}/questions/{self.first}", self.host)
        self.assertEqual(status, 200)

    def test_changes_broadcast_question_changed(self):
        with mock.patch("src.images.publish_event", new=mock.AsyncMock()) as publish:
            self.put(self.first, data_url(PNG))
            self.delete(self.first)
            self.put(self.first, "bad")
        code = self.session["code"]
        self.assertEqual(publish.await_args_list, [mock.call(code, "question_changed")] * 2)
