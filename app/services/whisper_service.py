from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import shutil
import os
import uuid

router = APIRouter()

# Load Faster-Whisper model (base/medium/small depending on system RAM)
model = WhisperModel("medium")

# Directory to store temporary audio files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/transcribe")
async def transcribe_audio_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Unsupported audio type")

    file_ext = os.path.splitext(file.filename)[1] or ".wav"
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_filepath = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        segments, info = model.transcribe(temp_filepath)
        transcription = " ".join([segment.text for segment in segments])
        detected_lang = info.language
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

    return {"transcription": transcription, "language": detected_lang}

# New helper for file-based transcription
async def transcribe_audio(file_path: str) -> dict:
    """
    Transcribe audio file and return both the transcription text and detected language.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    segments, info = model.transcribe(file_path)
    transcription = " ".join([segment.text for segment in segments])
    detected_lang = info.language  # ISO language code like 'en', 'ar', 'fr', etc.

    return {"text": transcription, "language": detected_lang}