"""Draws the join QR code shown on the presenter screen. It holds only the public join link, never the host key."""
import io
import re
from urllib.parse import urlsplit

import segno
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter()

CODE = re.compile(r"[A-Za-z0-9]{1,32}")


def join_link(origin: str, code: str) -> str:
    """The participant link for a session, e.g. https://abc.trycloudflare.com/join/ABC123."""
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("origin must be just a scheme and host")
    if not CODE.fullmatch(code):
        raise ValueError("bad session code")
    return f"{parts.scheme}://{parts.netloc}/join/{code.upper()}"


def qr_svg(text: str) -> bytes:
    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="svg", border=2, omitsize=True, xmldecl=False, dark="#000", light="#fff")
    return out.getvalue()


# The presenter page passes its own address (the public tunnel link), because the app cannot see it.
@router.get("/join/{code}/qr.svg", include_in_schema=False)
def join_qr(code: str, origin: str = Query(max_length=200)) -> Response:
    try:
        link = join_link(origin, code)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return Response(qr_svg(link), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=300"})
