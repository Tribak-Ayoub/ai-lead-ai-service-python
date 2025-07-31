from fastapi import APIRouter
from pydantic import BaseModel
import asyncio
from app.services.whisper_buffer_service import whisper_service
from app.services.intent_service import qualify_transcript
from app.routers.tts import synthesize_text

router = APIRouter()

class SegmentRequest(BaseModel):
    session_id: str
    pcm_path: str

@router.post("/process_segment")
async def process_segment(req: SegmentRequest):
    with open(req.pcm_path, "rb") as f:
        raw_pcm = f.read()

    await whisper_service.add_chunk(req.session_id, raw_pcm)

    await asyncio.sleep(1.2)  # wait for transcription

    qual = await qualify_transcript(req.session_id, "interested in demo")
    tts_bytes = await synthesize_text(qual["reply_text"], req.session_id)

    return {
        "reply_text": qual["reply_text"],
        "intent": qual["intent"],
        "lead_score": qual["lead_score"],
        "end": False
    }
