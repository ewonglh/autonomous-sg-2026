from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .db import init_db
from .routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CrowdPulse", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CrowdPulse</title></head>
  <body><main><h1>CrowdPulse</h1><p>Live questions for your event.</p><p>App is running. The first demo flow is ready to build.</p></main></body>
</html>"""


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}
