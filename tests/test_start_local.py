import subprocess
import unittest
from unittest.mock import MagicMock, Mock

from scripts import start_local


class StartLocalTests(unittest.TestCase):
    def setUp(self):
        self.run_command = Mock()
        self.wait_until_healthy = Mock(return_value=True)
        self.open_browser = Mock(return_value=True)
        self.messages = []

    def start(self):
        return start_local.start_local(
            run_command=self.run_command,
            wait_until_healthy=self.wait_until_healthy,
            open_browser=self.open_browser,
            report=self.messages.append,
        )

    def test_compose_starts_before_health_check_and_browser_open(self):
        self.assertEqual(self.start(), 0)
        self.run_command.assert_called_once_with(
            start_local.COMPOSE_COMMAND,
            cwd=start_local.REPO_ROOT,
            check=True,
        )
        self.wait_until_healthy.assert_called_once_with()
        self.open_browser.assert_called_once_with(start_local.HOST_URL)
        self.assertIn("Opened", self.messages[-1])

    def test_compose_failure_does_not_check_health_or_open_browser(self):
        self.run_command.side_effect = subprocess.CalledProcessError(1, "docker compose")

        self.assertEqual(self.start(), 1)

        self.wait_until_healthy.assert_not_called()
        self.open_browser.assert_not_called()
        self.assertIn("Docker Compose failed", self.messages[-1])
        self.assertNotIn("Opened", self.messages[-1])

    def test_missing_docker_does_not_open_browser(self):
        self.run_command.side_effect = FileNotFoundError("docker")

        self.assertEqual(self.start(), 1)

        self.wait_until_healthy.assert_not_called()
        self.open_browser.assert_not_called()
        self.assertIn("Docker was not found", self.messages[-1])

    def test_unhealthy_app_does_not_open_browser(self):
        self.wait_until_healthy.return_value = False

        self.assertEqual(self.start(), 1)

        self.open_browser.assert_not_called()
        self.assertIn("browser was not opened", self.messages[-1])

    def test_browser_failure_is_reported_without_claiming_it_opened(self):
        self.open_browser.return_value = False

        self.assertEqual(self.start(), 1)

        self.assertIn("browser did not open", self.messages[-1])
        self.assertNotIn("Opened", self.messages[-1])

    def test_browser_error_is_reported_without_claiming_it_opened(self):
        self.open_browser.side_effect = OSError("browser unavailable")

        self.assertEqual(self.start(), 1)

        self.assertIn("browser did not open", self.messages[-1])
        self.assertNotIn("Opened", self.messages[-1])


class HealthCheckTests(unittest.TestCase):
    def test_accepts_only_healthy_json_response(self):
        response = MagicMock(status=200)
        response.read.return_value = b'{"status":"ok"}'
        response.__enter__.return_value = response
        opener = Mock(return_value=response)

        self.assertTrue(start_local.app_is_healthy(opener))
        opener.assert_called_once_with(start_local.HEALTH_URL, timeout=2)

    def test_rejects_non_success_status_or_unhealthy_json(self):
        for status, body in ((503, b'{"status":"ok"}'), (200, b'{"status":"starting"}')):
            with self.subTest(status=status, body=body):
                response = MagicMock(status=status)
                response.read.return_value = body
                response.__enter__.return_value = response

                self.assertFalse(start_local.app_is_healthy(Mock(return_value=response)))

    def test_retries_until_healthy_then_stops(self):
        checks = Mock(side_effect=[False, True])
        clock = Mock(side_effect=[0, 0])
        sleep = Mock()

        self.assertTrue(start_local.wait_for_health(check_health=checks, clock=clock, sleep=sleep))
        self.assertEqual(checks.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_timeout_reports_unhealthy(self):
        checks = Mock(return_value=False)
        clock = Mock(side_effect=[0, 0, 10])
        sleep = Mock()

        self.assertFalse(start_local.wait_for_health(
            timeout_seconds=10,
            check_health=checks,
            clock=clock,
            sleep=sleep,
        ))
        self.assertEqual(checks.call_count, 2)


if __name__ == "__main__":
    unittest.main()
