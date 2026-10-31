from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .pages import STATIC_DIR
from .pages import router as pages_router
from .qa import router as qa_router
from .routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CrowdPulse", lifespan=lifespan)
app.include_router(router)
app.include_router(qa_router)
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
