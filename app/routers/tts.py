from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.services.piper_service import synthesize_with_piper

router = APIRouter()

@router.get("/tts/speak")
def speak(text: str = Query(..., min_length=1, description="Text to synthesize")):
    try:
        audio_path = synthesize_with_piper(text)
        return FileResponse(
            path=audio_path,
            media_type="audio/wav",
            filename="speech.wav",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unknown error: {e}")
