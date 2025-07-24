import os
import json
import re
from fastapi import HTTPException
import google.genai as genai

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set in environment or .env file")

# Initialize Google GenAI client
client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.0-flash-001"

# -----------------------------
# ✅ Quick intent check (manual)
# -----------------------------
def quick_intent_check(text: str) -> str:
    lower_text = text.lower()
    if re.search(r"\b(hi|hello|salam|hey)\b", lower_text):
        return "greeting"
    if len(lower_text.strip()) < 3 or re.search(r"\b(hmm|uh|...)\b", lower_text):
        return "unclear"
    return None  # Use Gemini if nothing matches

# ---------------------------------------
# 🔍 Main Gemini intent detection (async)
# ---------------------------------------
async def detect_intent(text: str) -> dict:
    prompt = (
        "You are a lead qualification assistant. "
        "Classify the following call transcription into one of these categories: "
        "interested, not interested, needs follow-up, invalid number, or other. "
        "Respond only with a JSON object: {\"intent\": <intent>, \"confidence\": <0-1>}\n\n"
        f"Transcription: \"{text}\""
    )

    try:
        from asyncio import to_thread
        response = await to_thread(
            lambda: client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"text": prompt}],
            )
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")

    content = response.text.strip()
    content = re.sub(r"^```json\s*|\s*```$", "", content.strip())

    try:
        intent_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from Gemini: {content}")

    return intent_json
