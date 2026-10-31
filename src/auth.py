import hashlib
import hmac

from fastapi import Header, HTTPException

from . import db
from .codes import RoomCode


def hash_host_key(host_key: str) -> str:
    return hashlib.sha256(host_key.encode("utf-8")).hexdigest()


def require_host_key(
    code: RoomCode, authorization: str | None = Header(default=None)
) -> None:
    scheme, separator, host_key = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not host_key.strip():
        _reject_host_key()

    stored_hash = db.get_host_key_hash(code)
    if stored_hash is None or not hmac.compare_digest(
        stored_hash, hash_host_key(host_key)
    ):
        _reject_host_key()


def _reject_host_key() -> None:
    raise HTTPException(
        status_code=401,
        detail="Invalid host key",
        headers={"WWW-Authenticate": "Bearer"},
    )
