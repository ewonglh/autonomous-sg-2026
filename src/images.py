"""HTTP routes for slide pictures."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from . import db, image_store, schemas
from .auth import require_host_key
from .codes import RoomCode
from .routes import publish_event, reject_expired_session

router = APIRouter(
    prefix="/api/sessions/{code}/questions/{qid}/image",
    dependencies=[Depends(reject_expired_session)],
)
NOT_FOUND = "Question not found"


@router.put("", response_model=schemas.Ok)
async def put_image(
    code: RoomCode, qid: int, body: schemas.ImageUpload, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    if len(body.data_url) > image_store.MAX_DATA_URL_LENGTH:
        raise HTTPException(status_code=413, detail="Picture is too big (max 1.5 MB)")
    image = image_store.decode_data_url(body.data_url)
    if image is None:
        raise HTTPException(
            status_code=422, detail="Send a PNG, JPEG, GIF or WebP image as a base64 data URL"
        )
    if not image_store.save_image(code, qid, *image):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    await publish_event(code, "question_changed")
    db.touch_session_activity(code)
    return schemas.Ok()


@router.delete("", response_model=schemas.Ok)
async def delete_image(
    code: RoomCode, qid: int, _key: str = Depends(require_host_key)
) -> schemas.Ok:
    if not image_store.delete_image(code, qid):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    await publish_event(code, "question_changed")
    db.touch_session_activity(code)
    return schemas.Ok()


@router.get("", response_class=Response)
def get_image(code: RoomCode, qid: int) -> Response:
    """Public, like the slide itself, so <img> tags on any screen can load it."""
    image = image_store.load_image(code, qid)
    if image is None:
        raise HTTPException(status_code=404, detail="Picture not found")
    media_type, data = image
    return Response(
        content=data,
        media_type=media_type,
        headers={
            # The URL carries a version, so a cached copy is never stale.
            "Cache-Control": "public, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
