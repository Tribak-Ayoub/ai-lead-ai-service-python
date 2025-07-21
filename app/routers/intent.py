from fastapi import APIRouter, Query
from app.services.intent_service import detect_intent

router = APIRouter()

@router.get("/intent/detect")
async def intent_detect(text: str = Query(..., min_length=1, description="Text to detect intent from")):
    result = await detect_intent(text)
    return result
