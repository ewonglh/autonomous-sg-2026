"""Start the local Compose app and open its host page after health succeeds."""
import json
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_COMMAND = ("docker", "compose", "up", "--build", "-d")
HEALTH_URL = "http://localhost:3000/healthz"
HOST_URL = "http://localhost:3000/host"
HEALTH_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 1


def app_is_healthy(open_url=urlopen):
    try:
        with open_url(HEALTH_URL, timeout=2) as response:
            return response.status == 200 and json.loads(response.read()) == {"status": "ok"}
    except (OSError, ValueError, URLError):
        return False


def wait_for_health(
    timeout_seconds=HEALTH_TIMEOUT_SECONDS,
    check_health=app_is_healthy,
    clock=time.monotonic,
    sleep=time.sleep,
):
    deadline = clock() + timeout_seconds
    while True:
        if check_health():
            return True
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        sleep(min(POLL_INTERVAL_SECONDS, remaining))


def start_local(run_command=None, wait_until_healthy=None, open_browser=None, report=None):
    run_command = run_command or subprocess.run
    wait_until_healthy = wait_until_healthy or wait_for_health
    open_browser = open_browser or webbrowser.open
    report = report or print

    try:
        run_command(COMPOSE_COMMAND, cwd=REPO_ROOT, check=True)
    except FileNotFoundError:
        report("Docker was not found. Install Docker Desktop and make sure docker is on PATH.")
        return 1
    except subprocess.CalledProcessError as error:
        report(f"Docker Compose failed with exit code {error.returncode}. Check that Docker Desktop is running.")
        return 1
    except OSError as error:
        report(f"Could not run Docker Compose: {error}")
        return 1

    if not wait_until_healthy():
        report(
            f"CrowdPulse did not become healthy within {HEALTH_TIMEOUT_SECONDS} seconds. "
            "The browser was not opened. Check Docker Compose logs and try again."
        )
        return 1

    try:
        browser_opened = open_browser(HOST_URL)
    except (OSError, webbrowser.Error):
        browser_opened = False
    if not browser_opened:
        report(f"CrowdPulse is healthy, but the browser did not open. Visit {HOST_URL}.")
        return 1

    report(f"CrowdPulse is ready. Opened {HOST_URL} in your browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(start_local())
