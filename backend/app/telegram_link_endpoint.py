# Example FastAPI endpoint for linking telegram chat to restaurant
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])

class LinkIn(BaseModel):
    code: str
    chat_id: int

@router.post("/link")  # POST /api/v1/telegram/link
async def link_chat(payload: LinkIn):
    # 1) find restaurant by one-time code (issued in LK)
    # 2) if found & valid -> save telegram_chat_id = payload.chat_id; invalidate code
    # 3) else raise HTTPException(404)
    # NOTE: integrate with your DB layer / ORM
    raise HTTPException(status_code=501, detail="Implement persistence here")
