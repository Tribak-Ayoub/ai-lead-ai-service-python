from fastapi import FastAPI
from app.routers import stt, tts

app = FastAPI()


app.include_router(stt.router, prefix="/stt")
app.include_router(tts.router, prefix="/tts")
