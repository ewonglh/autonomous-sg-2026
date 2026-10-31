"""Route stubs. They return contract-shaped dummy data; real logic comes in the next issue."""
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket
from fastapi.responses import PlainTextResponse

from . import schemas

router = APIRouter()


def require_host_key(authorization: str | None = Header(default=None)) -> str:
    # Stub: only checks that a bearer token is present. Real check compares its hash.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Host key required")
    return authorization.removeprefix("Bearer ")


@router.post("/api/sessions", response_model=schemas.SessionCreated)
def create_session() -> schemas.SessionCreated:
    return schemas.SessionCreated(code="ABC123", host_key="dummy-host-key")


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
    return schemas.QuestionCreated(id=1)


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
