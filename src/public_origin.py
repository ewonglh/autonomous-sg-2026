"""Find the public address assigned to the current Cloudflare Quick Tunnel."""
import os
import re
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()
LOG_FILE = Path(os.environ["TUNNEL_LOG_PATH"]) if os.environ.get("TUNNEL_LOG_PATH") else None
QUICK_TUNNEL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


def public_origin() -> str | None:
    if LOG_FILE is None:
        return None
    try:
        log = LOG_FILE.read_bytes()[-2_000_000:].decode("utf-8", errors="ignore")
    except OSError:
        return None
    matches = QUICK_TUNNEL.findall(log)
    return matches[-1].lower() if matches else None


@router.get("/public-origin", include_in_schema=False)
def get_public_origin() -> dict[str, str | bool | None]:
    return {"origin": public_origin(), "enabled": LOG_FILE is not None}
