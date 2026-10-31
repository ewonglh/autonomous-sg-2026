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


class JoinQrTests(ApiTestCase):
    def test_link_is_the_public_join_page_only(self):
        from src.qr import join_link
        self.assertEqual(join_link("https://abc.trycloudflare.com", "abc123"), "https://abc.trycloudflare.com/join/ABC123")

    def test_link_rejects_anything_but_a_plain_origin(self):
        from src.qr import join_link
        for origin, code in [("javascript:alert(1)", "ABC"), ("https://x.com/#key=secret", "ABC"), ("https://x.com/path", "ABC"), ("https://x.com", "../etc")]:
            with self.assertRaises(ValueError, msg=origin):
                join_link(origin, code)

    def test_qr_is_an_svg_image(self):
        from src.qr import qr_svg
        self.assertTrue(qr_svg("https://x.com/join/ABC").startswith(b"<svg"))
