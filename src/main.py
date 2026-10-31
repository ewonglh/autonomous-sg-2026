import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .errors import ApiError, api_error_handler
from .pages import STATIC_DIR
from .pages import router as pages_router
from .images import router as images_router
from .qa import router as qa_router
from .qr import router as qr_router
from .routes import close_finished_timers, router

logger = logging.getLogger(__name__)


async def run_slide_timers() -> None:
    """Close timed slides at zero even when nobody is asking for the state."""
    while True:
        await asyncio.sleep(0.5)
        try:
            await close_finished_timers()
        except Exception:
            logger.exception("Slide timer check failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    timer_task = asyncio.create_task(run_slide_timers())
    yield
    timer_task.cancel()


app = FastAPI(title="CrowdPulse", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.include_router(router)
app.include_router(qa_router)
app.include_router(images_router)
app.include_router(qr_router)
app.include_router(pages_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CrowdPulse</title></head>
  <body><main><h1>CrowdPulse</h1><p>Live questions for your event.</p><p><a href="/host">Start a session</a> · <a href="/join">Join with a code</a></p></main></body>
</html>"""


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}
