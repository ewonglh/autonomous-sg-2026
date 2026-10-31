"""HTTP routes for CrowdPulse sessions and polling."""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket
from fastapi.responses import PlainTextResponse

from . import db, schemas
from .auth import hash_host_key, require_host_key

router = APIRouter()


@router.post("/api/sessions", response_model=schemas.SessionCreated)
def create_session() -> schemas.SessionCreated:
    host_key = secrets.token_urlsafe(32)
    for _ in range(5):
        code = secrets.token_hex(4).upper()
        if db.create_session(code, hash_host_key(host_key)):
            return schemas.SessionCreated(code=code, host_key=host_key)
    raise HTTPException(status_code=503, detail="Could not create a unique session")


@router.get("/api/sessions/{code}/state", response_model=schemas.SessionState)
def get_state(code: str) -> schemas.SessionState:
    question = schemas.ActiveQuestion(
        id=1,
        type="multiple_choice",
        text="Dummy question?",
        options=[schemas.Option(id=1, label="Yes"), schemas.Option(id=2, label="No")],
        is_open=True,
        results_visible=False,
    )
    return schemas.SessionState(title="Dummy session", active_question=question)


@router.post("/api/sessions/{code}/questions", response_model=schemas.QuestionCreated)
def create_question(
    code: str, body: schemas.QuestionCreate, _key: str = Depends(require_host_key)
) -> schemas.QuestionCreated:
    question_id = db.create_question(code, body.type, body.text, body.options)
    if question_id is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.QuestionCreated(id=question_id)


@router.patch("/api/sessions/{code}/questions/{qid}", response_model=schemas.Ok)
def update_question(
    code: str, qid: int, body: schemas.QuestionUpdate, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    return schemas.Ok()


@router.post("/api/sessions/{code}/active", response_model=schemas.Ok)
def set_active(
    code: str, body: schemas.ActiveSet, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    return schemas.Ok()


@router.post("/api/sessions/{code}/questions/{qid}/responses", response_model=schemas.Ok)
def submit_response(
    code: str,
    qid: int,
    body: schemas.ResponseCreate,
    x_participant_id: str = Header(),
) -> schemas.Ok:
    return schemas.Ok()


@router.get("/api/sessions/{code}/results", response_model=schemas.Results)
def get_results(code: str, _key: str = Depends(require_host_key)) -> schemas.Results:
    return schemas.Results(
        results=[
            schemas.QuestionResults(
                question_id=1,
                type="multiple_choice",
                options=[
                    schemas.OptionCount(option_id=1, label="Yes", count=0),
                    schemas.OptionCount(option_id=2, label="No", count=0),
                ],
            ),
            schemas.QuestionResults(
                question_id=2,
                type="word_cloud",
                words=[schemas.WordCount(word="dummy", count=1)],
            ),
        ]
    )


CSV_HEADER = (
    "session_code,question_order,question_type,question_text,"
    "answer,participant_id,submitted_at_utc,qa_upvotes\r\n"
)


@router.get("/api/sessions/{code}/export.csv", response_class=PlainTextResponse)
def export_csv(code: str, _key: str = Depends(require_host_key)) -> PlainTextResponse:
    # Stub: header row only. The CSV issue writes the real export.
    return PlainTextResponse(CSV_HEADER, media_type="text/csv")


@router.websocket("/ws/{code}")
async def live_updates(websocket: WebSocket, code: str) -> None:
    # Stub: sends one example message, then closes. Real version broadcasts changes.
    await websocket.accept()
    await websocket.send_json({"type": "question_changed"})
    await websocket.close()
