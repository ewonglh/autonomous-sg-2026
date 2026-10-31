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
        for name in ["api.js", "charts.js", "qa.js", "timer.js", "image.js", "slides.js", "host.js", "host-dashboard.js", "join.js", "present.js", "style.css"]:
            self.assertEqual(self.request("GET", f"/static/{name}")[0], 200, name)

    def test_host_has_live_controls_and_dashboard_tabs(self):
        _, body, _ = self.request("GET", "/host/ABC123")
        for marker in [b'role="tablist"', b'id="panel-live"', b'id="panel-slides"', b'id="panel-results"', b'id="live-preview"', b'id="toggle-voting"', b'id="toggle-results"']:
            self.assertIn(marker, body)

    def test_presenter_shows_live_status(self):
        _, body, _ = self.request("GET", "/present/ABC123")
        self.assertIn(b'id="slide-state"', body)
        self.assertIn(b'id="timer"', body)

    def test_home_links_to_host_and_join(self):
        _, body, _ = self.request("GET", "/")
        self.assertIn(b'href="/host"', body)
        self.assertIn(b'href="/join"', body)
