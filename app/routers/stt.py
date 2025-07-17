from fastapi import APIRouter
from app.services.whisper_service import router as whisper_router

router = APIRouter()

# Include the whisper_service router under the /transcribe prefix or root of this router
router.include_router(whisper_router, prefix="", tags=["Speech-to-Text"])
