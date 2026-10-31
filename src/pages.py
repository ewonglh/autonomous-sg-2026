"""Serves the host, join and presenter pages. The pages talk to the JSON API themselves."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter()


def page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / f"{name}.html", media_type="text/html")


@router.get("/host", include_in_schema=False)
@router.get("/host/{code}", include_in_schema=False)
def host_page(code: str | None = None) -> FileResponse:
    return page("host")


@router.get("/join", include_in_schema=False)
@router.get("/join/{code}", include_in_schema=False)
def join_page(code: str | None = None) -> FileResponse:
    return page("join")


@router.get("/present/{code}", include_in_schema=False)
def present_page(code: str) -> FileResponse:
    return page("present")
