from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.intent_service import qualify_transcript

router = APIRouter()

class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1)

@router.post("/intent/detect")
async def intent_detect(request: IntentRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text input is empty or invalid")

    result = await qualify_transcript("", request.text)
    return result
