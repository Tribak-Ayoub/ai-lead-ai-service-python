import os
import json
import re
from fastapi import HTTPException
import google.genai as genai

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set in environment or .env file")

# Initialize Google GenAI client with API key (singleton for reuse)
client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-2.0-flash-001"  # current production-ready model

async def detect_intent(text: str) -> dict:
    prompt = (
        "You are a lead qualification assistant. "
        "Classify the following call transcription into one of these categories: "
        "interested, not interested, needs follow-up, invalid number, or other. "
        "Respond only with a JSON object: {\"intent\": <intent>, \"confidence\": <0-1>}\n\n"
        f"Transcription: \"{text}\""
    )

    try:
        # The API call is synchronous, so we run it in a threadpool to avoid blocking
        from asyncio import to_thread
        response = await to_thread(
            lambda: client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"text": prompt}],
            )
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")

    # Clean and normalize Gemini's response
    content = response.text.strip()
    content = re.sub(r"^```json\s*|\s*```$", "", content.strip())

    try:
        intent_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from Gemini: {content}")

    return intent_json
