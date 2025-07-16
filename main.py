from fastapi import FastAPI, UploadFile, File
from services import stt, tts, nlp
import os

app = FastAPI()

AUDIO_DIR = "audio_samples"
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...), lang: str = "en"):
    file_path = os.path.join(AUDIO_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    transcription = stt.transcribe_audio(file_path)
    intent = nlp.detect_intent(transcription)
    tts_path = os.path.join(AUDIO_DIR, f"response_{lang}.wav")
    tts.synthesize_text(intent, lang=lang, output_path=tts_path)

    return {
        "transcription": transcription,
        "intent": intent,
        "tts_path": tts_path
    }
