"""The host, join and presenter pages and their scripts are served."""
import unittest

from tests.test_contract import request


class PageTests(unittest.TestCase):
    def test_pages_are_html(self):
        for path, marker in [
            ("/host", b"host.js"),
            ("/host/ABC123", b"host.js"),
            ("/join", b"join.js"),
            ("/join/ABC123", b"join.js"),
            ("/present/ABC123", b"present.js"),
        ]:
            status, body, headers = request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["content-type"].startswith("text/html"), path)
            self.assertIn(marker, body, path)

    def test_static_files_are_served(self):
        for name in ["api.js", "charts.js", "qa.js", "timer.js", "host.js", "join.js", "present.js", "style.css"]:
            self.assertEqual(request("GET", f"/static/{name}")[0], 200, name)

    def test_home_links_to_host_and_join(self):
        _, body, _ = request("GET", "/")
        self.assertIn(b'href="/host"', body)
        self.assertIn(b'href="/join"', body)


if __name__ == "__main__":
    unittest.main()
