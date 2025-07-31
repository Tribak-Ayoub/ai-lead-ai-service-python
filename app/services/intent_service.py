# import os
# import json
# import re
# from fastapi import HTTPException
# import google.genai as genai

# API_KEY = os.getenv("GOOGLE_API_KEY")
# if not API_KEY:
#     raise RuntimeError("GOOGLE_API_KEY not set in environment or .env file")

# client = genai.Client(api_key=API_KEY)
# MODEL_NAME = "gemini-2.0-flash-001"

# # -------------------------
# # ✅ Quick rule-based check
# # -------------------------
# def quick_intent_check(text: str) -> dict | None:
#     lower = text.lower()
#     if re.search(r"\b(hi|hello|hey|salam|bonjour|salut)\b", lower):
#         return {"intent": "greeting", "confidence": 1.0}
#     if len(lower.strip()) < 3 or re.search(r"\b(hmm+|uh+|um+)\b|\.\.\.", lower):
#         return {"intent": "unclear", "confidence": 0.9}
#     return None

# # -----------------------------
# # 🤖 Gemini intent classifier
# # -----------------------------
# async def detect_intent(text: str) -> dict:
#     # First try manual pattern matching
#     fallback = quick_intent_check(text)
#     if fallback:
#         return fallback

#     prompt = (
#         "You are an AI assistant helping to qualify phone leads. "
#         "Based on the given transcription, classify the caller's intent into one of the following categories: "
#         "interested, not interested, needs follow-up, invalid number, or other.\n"
#         "Respond **only** with a valid JSON object in this format:\n"
#         "{\"intent\": \"interested\", \"confidence\": 0.93}\n"
#         "If you're unsure, still provide your best guess with low confidence.\n\n"
#         f"Transcription: \"{text}\""
#     )

#     try:
#         from asyncio import to_thread
#         response = await to_thread(
#             lambda: client.models.generate_content(
#                 model=MODEL_NAME,
#                 contents=[{"text": prompt}],
#             )
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

#     raw = response.text.strip()
#     raw = re.sub(r"^```json\s*|\s*```$", "", raw)

#     try:
#         intent_json = json.loads(raw)
#     except json.JSONDecodeError:
#         raise HTTPException(status_code=500, detail=f"Invalid JSON from Gemini: {raw}")

#     if not isinstance(intent_json, dict) or "intent" not in intent_json:
#         raise HTTPException(status_code=500, detail="Missing 'intent' in Gemini response")

#     return {
#         "intent": intent_json.get("intent", "unknown"),
#         "confidence": round(float(intent_json.get("confidence", 0.5)), 2)
#     }


async def qualify_transcript(session_id: str, transcript: str):
    lower = transcript.lower()
    score = 0
    intent = "unknown"
    entities = {"budget": None, "timeline": None}

    if "interested" in lower or "yes" in lower or "sure" in lower:
        intent = "interested"
        score += 2
    if "budget" in lower:
        intent = "has_budget"
        score += 1
        entities["budget"] = "mentioned"
    if "later" in lower or "not now" in lower:
        intent = "defer"
        score -= 1
    if "demo" in lower:
        intent = "wants_demo"
        score += 2

    next_action = "ask_budget" if not entities["budget"] else "confirm_demo"
    if intent == "defer":
        next_action = "close_or_followup"

    reply_text = {
        "ask_budget": "Can you tell me your expected budget range?",
        "confirm_demo": "Great, would you like to schedule a demo?",
        "close_or_followup": "Okay, I can follow up later. When would be a good time?",
    }.get(next_action, "Sorry, I didn't quite catch that. Could you clarify?")

    return {
        "intent": intent,
        "entities": entities,
        "lead_score": score,
        "next_action": next_action,
        "reply_text": reply_text,
        "end": False
    }
