"""HTTP routes for Q&A slides: audience questions and upvotes."""
from fastapi import APIRouter, Header, HTTPException

from . import qa_store, schemas
from .routes import (
    RESPONSE_SUBMISSION_LIMIT,
    enforce_rate_limit,
    parse_participant_id,
    publish_event,
)

router = APIRouter(prefix="/api/sessions/{code}/questions/{qid}/qa")
NOT_FOUND = "Q&A slide not found"


def participant(code: str, x_participant_id: str) -> str:
    participant_id = parse_participant_id(x_participant_id)
    enforce_rate_limit(("qa", code, participant_id), RESPONSE_SUBMISSION_LIMIT)
    return participant_id


@router.get("", response_model=schemas.QaList)
def list_items(
    code: str, qid: int, x_participant_id: str | None = Header(default=None)
) -> schemas.QaList:
    participant_id = parse_participant_id(x_participant_id) if x_participant_id else None
    items = qa_store.list_items(code, qid, participant_id)
    if items is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return schemas.QaList(items=items)


@router.post("", response_model=schemas.QuestionCreated)
async def add_item(
    code: str, qid: int, body: schemas.QaCreate, x_participant_id: str = Header()
) -> schemas.QuestionCreated:
    result = qa_store.add_item(code, qid, participant(code, x_participant_id), body.text)
    if result == "not_found":
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if result == "closed":
        raise HTTPException(status_code=400, detail="Q&A is closed for new questions")
    await publish_event(code, "qa_changed")
    return schemas.QuestionCreated(id=result)


@router.post("/{item_id}/upvote", response_model=schemas.Ok)
async def upvote(
    code: str, qid: int, item_id: int, x_participant_id: str = Header()
) -> schemas.Ok:
    result = qa_store.add_upvote(code, qid, item_id, participant(code, x_participant_id))
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Q&A question not found")
    if result == "duplicate":
        raise HTTPException(status_code=409, detail="Already upvoted")
    await publish_event(code, "qa_changed")
    return schemas.Ok()


@router.delete("/{item_id}/upvote", response_model=schemas.Ok)
async def remove_upvote(
    code: str, qid: int, item_id: int, x_participant_id: str = Header()
) -> schemas.Ok:
    participant_id = participant(code, x_participant_id)
    if not qa_store.remove_upvote(code, qid, item_id, participant_id):
        raise HTTPException(status_code=404, detail="Q&A question not found")
    await publish_event(code, "qa_changed")
    return schemas.Ok()
