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
    """
    Improved conversation flow with state tracking
    """
    lower = transcript.lower()
    score = 0
    intent = "unknown"
    entities = {"budget": None, "timeline": None}
    
    print(f"[INTENT] Processing transcript: '{transcript}'")
    print(f"[INTENT] Lowercased: '{lower}'")
    
    # Check for budget-related responses first
    budget_keywords = ["thousand", "k", "dollar", "budget", "hundred", "million", "afford"]
    budget_numbers = ["1", "2", "3", "4", "5", "10", "20", "50", "100", "500", "1000"]
    
    has_budget_mention = any(keyword in lower for keyword in budget_keywords)
    has_numbers = any(num in lower for num in budget_numbers)
    
    if has_budget_mention or has_numbers:
        intent = "has_budget"
        score += 2
        entities["budget"] = "mentioned"
        print(f"[INTENT] Detected budget mention")
    
    # Check for positive responses
    positive_keywords = ["yes", "sure", "ok", "okay", "interested", "want", "need", "like"]
    if any(keyword in lower for keyword in positive_keywords):
        if intent == "unknown":
            intent = "interested"
        score += 1
        print(f"[INTENT] Detected positive response")
    
    # Check for negative responses (be more specific to avoid false positives)
    negative_phrases = ["not interested", "don't want", "don't need", "maybe later", "not now", "no thanks", "not for me"]
    is_negative = False
    
    # Check for explicit "no" at the beginning or as a standalone response
    if lower.strip().startswith("no ") or lower.strip() == "no":
        is_negative = True
    
    # Check for negative phrases
    for phrase in negative_phrases:
        if phrase in lower:
            is_negative = True
            break
    
    if is_negative:
        intent = "not_interested"
        score -= 2
        print(f"[INTENT] Detected negative response")
    
    # Check for demo requests
    demo_keywords = ["demo", "demonstration", "show me", "see it", "preview"]
    if any(keyword in lower for keyword in demo_keywords):
        intent = "wants_demo"
        score += 2
        print(f"[INTENT] Detected demo interest")
    
    # Check for timeline mentions
    timeline_keywords = ["soon", "asap", "urgent", "this week", "this month", "next week", "next month"]
    if any(keyword in lower for keyword in timeline_keywords):
        entities["timeline"] = "mentioned"
        score += 1
        print(f"[INTENT] Detected timeline mention")
    
    # Determine next action and response based on current state
    print(f"[INTENT] Current intent: {intent}, score: {score}")
    
    if intent == "not_interested":
        next_action = "close_politely"
        reply_text = "I understand. Thank you for your time. Have a great day!"
        end = True
    elif intent == "has_budget":
        next_action = "offer_demo"
        reply_text = "Great! Based on your budget, I think our solution would be a perfect fit. Would you like to see a quick demo?"
        end = False
    elif intent == "wants_demo":
        next_action = "schedule_demo"
        reply_text = "Excellent! I'd be happy to show you a demo. When would be a good time for you?"
        end = False
    elif intent == "interested":
        # If they're interested but haven't mentioned budget, ask about it
        next_action = "ask_budget"
        reply_text = "That's great to hear! To help me recommend the best solution, could you share what budget range you're working with?"
        end = False
    else:
        # Handle unclear or unknown responses
        next_action = "clarify"
        reply_text = "I want to make sure I understand your needs. Are you interested in learning more about our solution?"
        end = False
    
    result = {
        "intent": intent,
        "entities": entities,
        "lead_score": score,
        "next_action": next_action,
        "reply_text": reply_text,
        "end": end
    }
    
    print(f"[INTENT] Final result: {result}")
    return result