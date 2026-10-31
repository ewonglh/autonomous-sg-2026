"""HTTP routes for CrowdPulse sessions and polling."""
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket
from fastapi.responses import Response

from . import csv_export, db, schemas
from .codes import RoomCode
from .auth import hash_host_key, require_host_key
from .limits import RateLimiter

router = APIRouter()
SESSION_CREATION_LIMIT = 5
RESPONSE_SUBMISSION_LIMIT = 10
rate_limiter = RateLimiter()


def enforce_rate_limit(key: tuple[str, ...], limit: int) -> None:
    retry_after = rate_limiter.check_request(key, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def parse_participant_id(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="X-Participant-Id must be a UUID",
        ) from exc


@router.post("/api/sessions", response_model=schemas.SessionCreated)
def create_session() -> schemas.SessionCreated:
    enforce_rate_limit(("session_creation",), SESSION_CREATION_LIMIT)
    host_key = secrets.token_urlsafe(32)
    for _ in range(5):
        code = secrets.token_hex(4).upper()
        if db.create_session(code, hash_host_key(host_key)):
            return schemas.SessionCreated(code=code, host_key=host_key)
    raise HTTPException(status_code=503, detail="Could not create a unique session")


@router.get("/api/sessions/{code}/state", response_model=schemas.SessionState)
def get_state(code: RoomCode) -> schemas.SessionState:
    state = db.get_session_state(code)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.SessionState(**state)


@router.post("/api/sessions/{code}/questions", response_model=schemas.QuestionCreated)
def create_question(
    code: RoomCode, body: schemas.QuestionCreate, _key: str = Depends(require_host_key)
) -> schemas.QuestionCreated:
    question_id = db.create_question(code, body.type, body.text, body.options)
    if question_id is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.QuestionCreated(id=question_id)


@router.patch("/api/sessions/{code}/questions/{qid}", response_model=schemas.Ok)
def update_question(
    code: RoomCode, qid: int, body: schemas.QuestionUpdate, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    changes = body.model_dump(exclude_unset=True)
    if changes and not db.update_question_state(code, qid, changes):
        raise HTTPException(status_code=404, detail="Question not found")
    return schemas.Ok()


@router.post("/api/sessions/{code}/active", response_model=schemas.Ok)
def set_active(
    code: RoomCode, body: schemas.ActiveSet, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    if not db.set_active_question(code, body.question_id):
        raise HTTPException(status_code=404, detail="Question not found")
    return schemas.Ok()


@router.post("/api/sessions/{code}/questions/{qid}/responses", response_model=schemas.Ok)
def submit_response(
    code: RoomCode,
    qid: int,
    body: schemas.ResponseCreate,
    x_participant_id: str = Header(),
) -> schemas.Ok:
    participant_id = parse_participant_id(x_participant_id)
    enforce_rate_limit(
        ("responses", code, participant_id), RESPONSE_SUBMISSION_LIMIT
    )
    if body.option_id is not None:
        if body.text is not None:
            raise HTTPException(
                status_code=422,
                detail="Multiple-choice responses need an option_id only",
            )
        result = db.save_multiple_choice_response(
            code, qid, participant_id, body.option_id
        )
        if result == "not_found":
            raise HTTPException(status_code=404, detail="Session or question not found")
        if result == "wrong_type":
            raise HTTPException(
                status_code=422,
                detail="Question does not accept multiple-choice responses",
            )
        if result == "closed":
            raise HTTPException(status_code=409, detail="Question is closed")
        if result == "invalid_option":
            raise HTTPException(
                status_code=422, detail="Option does not belong to this question"
            )
        if result == "duplicate":
            raise HTTPException(
                status_code=409, detail="Participant has already responded"
            )
        return schemas.Ok()

    if body.text is None or len(body.text) > 200:
        raise HTTPException(status_code=422, detail="Invalid word-cloud response")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Response text must not be blank")

    result = db.save_word_cloud_response(code, qid, participant_id, text)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Question not found in session")
    if result == "wrong_type":
        raise HTTPException(
            status_code=422, detail="Question does not accept text responses"
        )
    if result == "closed":
        raise HTTPException(status_code=409, detail="Question is closed")
    if result == "limit_reached":
        raise HTTPException(status_code=409, detail="Response limit reached")
    return schemas.Ok()


@router.get(
    "/api/sessions/{code}/results",
    response_model=schemas.Results,
    response_model_exclude_none=True,
)
def get_results(code: RoomCode, _key: str = Depends(require_host_key)) -> schemas.Results:
    results = [schemas.QuestionResults(**result) for result in db.get_session_results(code)]
    return schemas.Results(results=results)


@router.get("/api/sessions/{code}/export.csv", response_class=Response)
def export_csv(code: RoomCode, _key: str = Depends(require_host_key)) -> Response:
    conn = db.connect()
    try:
        session = conn.execute("SELECT id FROM sessions WHERE code = ?", (code,)).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        responses = conn.execute(
            """SELECT s.code, q.position, q.type, q.text,
                      COALESCE(o.label, r.text, '') AS answer,
                      r.participant_id, r.created_at
               FROM responses r
               JOIN questions q ON q.id = r.question_id
               JOIN sessions s ON s.id = q.session_id
               LEFT JOIN options o ON o.id = r.option_id
               WHERE s.id = ?
               ORDER BY q.position, r.created_at, r.id""",
            (session["id"],),
        ).fetchall()
    finally:
        conn.close()

    rows = (
        (row["code"], row["position"], row["type"], row["text"], row["answer"],
         row["participant_id"], row["created_at"], "")
        for row in responses
    )
    return Response(
        content=csv_export.render_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{code}.csv"'},
    )


@router.websocket("/ws/{code}")
async def live_updates(websocket: WebSocket, code: RoomCode) -> None:
    # Stub: sends one example message, then closes. Real version broadcasts changes.
    await websocket.accept()
    await websocket.send_json({"type": "question_changed"})
    await websocket.close()
