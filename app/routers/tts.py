from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from app.services.piper_service import synthesize_with_piper, synthesize_bytes
from app.core.config import settings

import os
import tempfile

router = APIRouter()

@router.get("/tts/speak")
def speak(text: str = Query(..., min_length=1), lang: str = Query(None)):
    try:
        audio_path = synthesize_with_piper(text, lang=lang or settings.default_tts_lang)
        return FileResponse(audio_path, media_type="audio/wav", filename="speech.wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tts/speak_bytes")
def speak_bytes(text: str, lang: str = Query(None)):
    try:
        audio_bytes = synthesize_bytes(text, lang=lang or settings.default_tts_lang)
        return JSONResponse({"length": len(audio_bytes)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add this helper function so other modules can import it
async def synthesize_text(text: str, session_id: str = None, lang: str = None) -> bytes:
    """
    Helper function to synthesize text to audio bytes (async compatible).
    `session_id` is optional, included to match your usage.
    """
    # This function uses the sync synthesize_bytes, so run in thread
    import asyncio
    loop = asyncio.get_running_loop()
    audio_bytes = await loop.run_in_executor(None, lambda: synthesize_bytes(text, lang or settings.default_tts_lang))
    return audio_bytes
