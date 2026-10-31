"""HTTP routes for CrowdPulse sessions and polling."""
import secrets
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response

from . import csv_export, db, question_order, schemas
from .auth import hash_host_key, require_host_key
from .limits import RateLimiter

router = APIRouter()
SESSION_CREATION_LIMIT = 5
RESPONSE_SUBMISSION_LIMIT = 10
rate_limiter = RateLimiter()
live_connections: dict[str, set[WebSocket]] = {}


def enforce_rate_limit(key: tuple[str, ...], limit: int) -> None:
    retry_after = rate_limiter.check_request(key, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


async def publish_event(code: str, event: str) -> None:
    connections = live_connections.get(code, set())
    for websocket in tuple(connections):
        try:
            await websocket.send_json({"type": event})
        except (RuntimeError, WebSocketDisconnect):
            connections.discard(websocket)
    if not connections:
        live_connections.pop(code, None)


def parse_participant_id(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="X-Participant-Id must be a UUID",
        ) from exc


def reject_expired_session(code: str) -> None:
    if db.session_is_expired(code):
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/api/sessions", response_model=schemas.SessionCreated)
def create_session(
    body: schemas.SessionCreate | None = None,
) -> schemas.SessionCreated:
    enforce_rate_limit(("session_creation",), SESSION_CREATION_LIMIT)
    host_key = secrets.token_urlsafe(32)
    title = body.title if body is not None else "Untitled session"
    for _ in range(5):
        code = secrets.token_hex(4).upper()
        if db.create_session(code, hash_host_key(host_key), title):
            return schemas.SessionCreated(code=code, host_key=host_key)
    raise HTTPException(status_code=503, detail="Could not create a unique session")


@router.get(
    "/api/sessions/{code}/state",
    response_model=schemas.SessionState,
    dependencies=[Depends(reject_expired_session)],
)
def get_state(code: str) -> schemas.SessionState:
    state = db.get_session_state(code)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    active_question = state["active_question"]
    # Q&A slides ignore results_visible; their items come from the Q&A routes.
    if (
        active_question
        and active_question["results_visible"]
        and active_question["type"] != "qa"
    ):
        result = next(
            (
                item
                for item in db.get_session_results(code)
                if item["question_id"] == active_question["id"]
            ),
            None,
        )
        if result is not None:
            active_question["results"] = (
                {"options": result["options"]}
                if result["type"] == "multiple_choice"
                else {"words": result["words"]}
            )
    response = schemas.SessionState(**state)
    db.touch_session_activity(code)
    return response


@router.get(
    "/api/sessions/{code}/questions",
    response_model=schemas.QuestionList,
    dependencies=[Depends(reject_expired_session)],
)
def get_questions(
    code: str, _key: str = Depends(require_host_key)
) -> schemas.QuestionList:
    questions = db.get_session_questions(code)
    if questions is None:
        raise HTTPException(status_code=404, detail="Session not found")
    response = schemas.QuestionList(**questions)
    db.touch_session_activity(code)
    return response


@router.post(
    "/api/sessions/{code}/questions",
    response_model=schemas.QuestionCreated,
    dependencies=[Depends(reject_expired_session)],
)
async def create_question(
    code: str, body: schemas.QuestionCreate, _key: str = Depends(require_host_key)
) -> schemas.QuestionCreated:
    question_id = db.create_question(
        code, body.type, body.text, body.options, body.chart
    )
    if question_id is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await publish_event(code, "question_changed")
    response = schemas.QuestionCreated(id=question_id)
    db.touch_session_activity(code)
    return response


@router.patch(
    "/api/sessions/{code}/questions/{qid}",
    response_model=schemas.Ok,
    dependencies=[Depends(reject_expired_session)],
)
async def update_question(
    code: str, qid: int, body: schemas.QuestionUpdate, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    changes = body.model_dump(exclude_unset=True)
    if changes and not db.update_question_state(code, qid, changes):
        raise HTTPException(status_code=404, detail="Question not found")
    if changes:
        await publish_event(code, "question_changed")
    response = schemas.Ok()
    db.touch_session_activity(code)
    return response


@router.put(
    "/api/sessions/{code}/questions/order",
    response_model=schemas.Ok,
    dependencies=[Depends(reject_expired_session)],
)
async def reorder_questions(
    code: str, body: schemas.QuestionOrder, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    result = question_order.reorder_questions(code, body.question_ids)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
    if result == "mismatch":
        raise HTTPException(
            status_code=422,
            detail="question_ids must list every question in the session exactly once",
        )
    await publish_event(code, "question_changed")
    db.touch_session_activity(code)
    return schemas.Ok()


@router.post(
    "/api/sessions/{code}/active",
    response_model=schemas.Ok,
    dependencies=[Depends(reject_expired_session)],
)
async def set_active(
    code: str, body: schemas.ActiveSet, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    if not db.set_active_question(code, body.question_id):
        raise HTTPException(status_code=404, detail="Question not found")
    await publish_event(code, "question_changed")
    response = schemas.Ok()
    db.touch_session_activity(code)
    return response


@router.post(
    "/api/sessions/{code}/questions/{qid}/responses",
    response_model=schemas.Ok,
    dependencies=[Depends(reject_expired_session)],
)
async def submit_response(
    code: str,
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
        if result == "accepted":
            await publish_event(code, "results_changed")
        response = schemas.Ok()
        db.touch_session_activity(code)
        return response

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
    if result == "saved":
        await publish_event(code, "results_changed")
    response = schemas.Ok()
    db.touch_session_activity(code)
    return response


@router.get(
    "/api/sessions/{code}/results",
    response_model=schemas.Results,
    response_model_exclude_none=True,
    dependencies=[Depends(reject_expired_session)],
)
def get_results(code: str, _key: str = Depends(require_host_key)) -> schemas.Results:
    results = [schemas.QuestionResults(**result) for result in db.get_session_results(code)]
    response = schemas.Results(results=results)
    db.touch_session_activity(code)
    return response


@router.get(
    "/api/sessions/{code}/export.csv",
    response_class=Response,
    dependencies=[Depends(reject_expired_session)],
)
def export_csv(code: str, _key: str = Depends(require_host_key)) -> Response:
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
    content = csv_export.render_csv(rows)
    db.touch_session_activity(code)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{code}.csv"'},
    )


@router.websocket("/ws/{code}")
async def live_updates(websocket: WebSocket, code: str) -> None:
    await websocket.accept()
    connections = live_connections.setdefault(code, set())
    connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connections.discard(websocket)
        if not connections:
            live_connections.pop(code, None)
