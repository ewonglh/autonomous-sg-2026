import json
import os
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def main() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError("app exited before becoming ready")
            try:
                with urlopen(f"{base}/healthz", timeout=1) as response:
                    health = json.loads(response.read())
                with urlopen(base, timeout=1) as response:
                    content_type = response.headers.get("Content-Type", "")
                    page = response.read().decode("utf-8")
                assert health == {"status": "ok"}
                assert content_type.startswith("text/html")
                assert "<title>CrowdPulse</title>" in page
                assert "<h1>CrowdPulse</h1>" in page
                assert "Live questions for your event." in page
                print("smoke: health endpoint and home page are working")
                return 0
            except (OSError, ValueError):
                time.sleep(0.1)
        raise RuntimeError("app did not become ready")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
