import asyncio
import json
import re
import logging
from typing import Dict, Any

import aiohttp

from app.core.config import settings

# -------------------------
# Quick rule-based checks
# -------------------------
def quick_intent_check(text: str) -> Dict[str, Any] | None:
    lower = text.lower().strip()
    if len(lower) < 2 or re.search(r"\b(hmm+|uh+|um+)\b|\.\.\.", lower):
        return {
            "intent": "unclear",
            "confidence": 0.6,
            "response_text": "I didn't quite catch that. Could you clarify?",
            "next_action": "clarify",
            "end": False
        }
    if re.search(r"\b(hi|hello|hey|salam|bonjour|good morning|good afternoon)\b", lower):
        return {
            "intent": "greeting",
            "confidence": 0.7,  # lowered so Gemini can override if there's more content
            "response_text": "Hi! Thanks for taking the call. Are you interested in learning more about our solution?",
            "next_action": "ask_interest",
            "end": False
        }
    if re.search(r"\b(not interested|don't want|don't need|no thanks|maybe later|not now)\b", lower):
        return {
            "intent": "not_interested",
            "confidence": 0.95,
            "response_text": "I understand. Thank you for your time. Have a great day!",
            "next_action": "close_politely",
            "end": True
        }
    if re.search(r"\b(demo|demonstration|show me|see it|preview)\b", lower):
        return {
            "intent": "wants_demo",
            "confidence": 0.9,
            "response_text": "Excellent! I'd be happy to show you a demo. When would be a good time for you?",
            "next_action": "schedule_demo",
            "end": False
        }
    if re.search(r"\b(\$?\d+(\.\d+)?\s*(k|thousand|million)?|\bbudget\b|\bafford\b)\b", lower):
        return {
            "intent": "has_budget",
            "confidence": 0.8,
            "response_text": "Great! Based on your budget, I think our solution would be a perfect fit. Would you like to see a quick demo?",
            "next_action": "offer_demo",
            "end": False
        }
    return None


# -------------------------
# Gemini integration
# -------------------------
async def call_gemini_intent_classifier(transcript: str) -> Dict[str, Any]:
    """
    Call Gemini Generative Language API to classify intent and get reply.
    """
    # Build URL here to ensure API key is injected cleanly
    api_key = settings.google_api_key
    model = settings.gemini_model
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateMessage?key={api_key}"

    prompt = f"""
You are a lead qualification assistant on a sales call. The caller said: "{transcript}"

Classify their intent into one of these categories:
- interested
- not_interested
- wants_demo
- has_budget
- unclear

Also infer if there's a timeline or budget signal.

Then produce a next action and a concise conversational reply that moves the call forward.

Respond with a JSON object exactly in this format:
{{
  "intent": "<one of the above>",
  "confidence": 0.0,
  "entities": {{"budget": "<if present or null>", "timeline": "<if present or null>"}},
  "next_action": "<ask_budget|offer_demo|schedule_demo|close_politely|clarify>",
  "reply_text": "<what to say to the caller next>",
  "end": <true|false>
}}
If you're unsure, pick the best guess and set confidence low.
"""

    body = {
        "messages": [
            {"role": "user", "content": {"text": prompt}}
        ],
        "temperature": 0.3,
        "max_output_tokens": 300,
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(gemini_url, headers=headers, json=body, timeout=10) as resp:
                raw = await resp.text()
                if resp.status != 200:
                    logging.warning(f"[Gemini] Non-200 response: {resp.status} body: {raw}")
                    raise RuntimeError(f"Gemini API returned status {resp.status}")
                data = await resp.json()
    except Exception as e:
        logging.error(f"[Gemini] Exception calling API: {e}")
        return {
            "intent": "unclear",
            "confidence": 0.4,
            "entities": {"budget": None, "timeline": None},
            "next_action": "clarify",
            "reply_text": "I want to make sure I understood — could you tell me more about what you're looking for?",
            "end": False
        }

    # Extract text output; adapt based on actual response schema
    raw_text = ""
    try:
        if "output" in data and isinstance(data["output"], list):
            for item in data["output"]:
                if isinstance(item.get("content"), list):
                    for c in item["content"]:
                        if "text" in c:
                            raw_text += c["text"]
        elif "candidates" in data and isinstance(data["candidates"], list):
            cand = data["candidates"][0]
            if isinstance(cand.get("content"), list):
                for c in cand["content"]:
                    if "text" in c:
                        raw_text += c["text"]
        else:
            raw_text = data.get("text", "")
    except Exception as e:
        logging.error(f"[Gemini] Failed to parse response shape: {e}; full payload: {data}")
        raw_text = ""

    raw_text = raw_text.strip()
    if not raw_text:
        logging.warning("[Gemini] Empty model response, falling back")
        return {
            "intent": "unclear",
            "confidence": 0.4,
            "entities": {"budget": None, "timeline": None},
            "next_action": "clarify",
            "reply_text": "Could you say that again? I want to understand your needs.",
            "end": False
        }

    # Strip markdown fences if any
    raw_text = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        intent_json = json.loads(raw_text)
    except json.JSONDecodeError:
        logging.error(f"[Gemini] JSON decode error on '{raw_text}'")
        return {
            "intent": "unclear",
            "confidence": 0.5,
            "entities": {"budget": None, "timeline": None},
            "next_action": "clarify",
            "reply_text": raw_text or "I didn't quite get that; could you clarify?",
            "end": False
        }

    intent = intent_json.get("intent", "unknown")
    confidence = float(intent_json.get("confidence", 0.0))
    entities = intent_json.get("entities", {}) if isinstance(intent_json.get("entities", {}), dict) else {}
    next_action = intent_json.get("next_action", "clarify")
    reply_text = intent_json.get("reply_text", "")
    end = bool(intent_json.get("end", False))

    return {
        "intent": intent,
        "confidence": round(confidence, 2),
        "entities": {
            "budget": entities.get("budget"),
            "timeline": entities.get("timeline"),
        },
        "next_action": next_action,
        "reply_text": reply_text or "Could you tell me more about that?",
        "end": end
    }


# -------------------------
# Top-level qualification
# -------------------------
async def qualify_transcript(session_id: str, transcript: str) -> Dict[str, Any]:
    """
    Main qualification: quick rules first, then Gemini for richer understanding.
    """
    print(f"[INTENT] Received transcript for session {session_id}: '{transcript}'")

    # Try rule-based first
    quick = quick_intent_check(transcript)
    if quick and quick.get("confidence", 0) >= 0.9:
        result = {
            "intent": quick["intent"],
            "entities": {"budget": None, "timeline": None},
            "lead_score": 0,
            "next_action": quick["next_action"],
            "reply_text": quick["response_text"],
            "end": quick.get("end", False)
        }
        print(f"[INTENT] Quick rule result: {result}")
        return result

    # Otherwise call Gemini
    gemini_result = await call_gemini_intent_classifier(transcript)

    # Heuristic lead score
    lead_score = 0
    if gemini_result["intent"] in ("interested", "has_budget", "wants_demo"):
        lead_score += 1
    if gemini_result["intent"] == "has_budget":
        lead_score += 1
    if gemini_result["intent"] == "not_interested":
        lead_score -= 1

    result = {
        "intent": gemini_result["intent"],
        "entities": gemini_result["entities"],
        "lead_score": lead_score,
        "next_action": gemini_result["next_action"],
        "reply_text": gemini_result["reply_text"],
        "end": gemini_result["end"]
    }

    print(f"[INTENT] Gemini-enhanced result: {result}")
    return result
