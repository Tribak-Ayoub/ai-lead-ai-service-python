# app/services/whisper_service.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import shutil
import os
import uuid

router = APIRouter()

# Load Faster-Whisper model (base/medium/small depending on system RAM)
model = WhisperModel("base")

# Directory to store temporary audio files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    print("Received content_type:", file.content_type)  # DEBUG
    if not file.content_type or not file.content_type.startswith("audio/"):
       raise HTTPException(status_code=400, detail="Unsupported audio type")


    file_ext = os.path.splitext(file.filename)[1] or ".wav"
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_filepath = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        with open(temp_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Transcribe the uploaded audio
        segments, _ = model.transcribe(temp_filepath)
        transcription = " ".join([segment.text for segment in segments])

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        # Always clean up temp file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

    return {"transcription": transcription}
