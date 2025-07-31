# import os
# from dotenv import load_dotenv

# # Get the root folder path where your .env file exists
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# # Explicitly load .env from the root folder
# load_dotenv(os.path.join(BASE_DIR, ".env"))

# # print("API key on startup:", os.getenv("GOOGLE_API_KEY"))

# from fastapi import FastAPI
# from app.routers import stt, tts, intent

# app = FastAPI()

# app.include_router(stt.router, prefix="/stt")
# app.include_router(tts.router, prefix="/tts")
# app.include_router(intent.router, tags=["Intent Detection"])

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.routers import ws_stream, tts, intent, one_shot

app = FastAPI()

app.include_router(ws_stream.router)
app.include_router(tts.router, prefix="/api")
app.include_router(intent.router, prefix="/api")
app.include_router(one_shot.router, prefix="/api")
