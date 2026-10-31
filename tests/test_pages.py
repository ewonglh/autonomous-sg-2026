"""The host, join and presenter pages and their scripts are served."""
from support import ApiTestCase


class PageTests(ApiTestCase):
    def test_pages_are_html(self):
        for path, marker in [
            ("/host", b"host.js"),
            ("/host/ABC123", b"host.js"),
            ("/join", b"join.js"),
            ("/join/ABC123", b"join.js"),
            ("/present/ABC123", b"present.js"),
        ]:
            status, body, headers = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["content-type"].startswith("text/html"), path)
            self.assertIn(marker, body, path)

    def test_static_files_are_served(self):
        for name in ["api.js", "charts.js", "qa.js", "timer.js", "image.js", "slides.js", "host.js", "join.js", "present.js", "style.css"]:
            self.assertEqual(self.request("GET", f"/static/{name}")[0], 200, name)

    def test_home_links_to_host_and_join(self):
        _, body, _ = self.request("GET", "/")
        self.assertIn(b'href="/host"', body)
        self.assertIn(b'href="/join"', body)
