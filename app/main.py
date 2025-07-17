# app/main.py

from fastapi import FastAPI
from app.services import whisper_service

app = FastAPI()

app.include_router(whisper_service.router, prefix="/stt", tags=["Speech-to-Text"])
