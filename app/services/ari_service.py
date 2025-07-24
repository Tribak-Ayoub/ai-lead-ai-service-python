import os
import json
import re
import time
import threading
import subprocess
import asyncio
import requests
import websocket

from dotenv import load_dotenv
load_dotenv()

from app.services.whisper_service import transcribe_audio
from app.services.piper_service import synthesize_with_piper as generate_tts

# ---------------------- CONFIG ----------------------
ARI_URL = os.getenv("ARI_BASE_URL")
ARI_USERNAME = os.getenv("ARI_USERNAME")
ARI_PASSWORD = os.getenv("ARI_PASSWORD")
APP_NAME = "ai-assistant"
AUTH = (ARI_USERNAME, ARI_PASSWORD)
ARI_WS_URL = f"ws://localhost:8088/ari/events?api_key={ARI_USERNAME}:{ARI_PASSWORD}&app={APP_NAME}"

SOUND_FILE_NAME = "ai_response"
SOUND_FILE_PATH = f"/var/lib/asterisk/sounds/ai/{SOUND_FILE_NAME}.wav"
RECORD_DIR = "/var/spool/asterisk/recording"

RESPONSE_TEMPLATES = {
    "greeting": "Hello! Thank you for calling. How can I assist you today?",
    "interested": "That's great to hear! I'm glad you're interested. An agent will follow up with you shortly.",
    "not interested": "No worries at all. Thank you for your time, and feel free to contact us anytime.",
    "needs follow-up": "Sure thing. We’ll get back to you with more details as soon as possible.",
    "invalid number": "Hmm, I’m having trouble identifying the number. Could you try calling again later?",
    "unclear": "Sorry, I didn’t quite catch that. Could you please repeat it more clearly?",
    "other": "Thanks for your message. Can you tell me a bit more about what you're looking for?",
    "goodbye": "Thanks again for calling. Have a great day!"
}

# ---------------------- API WRAPPERS ----------------------
def api_get(path):
    url = f"{ARI_URL}{path}"
    r = requests.get(url, auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    url = f"{ARI_URL}{path}"
    r = requests.post(url, json=data, auth=AUTH)
    r.raise_for_status()
    return r.json() if r.content else None

def api_delete(path):
    url = f"{ARI_URL}{path}"
    r = requests.delete(url, auth=AUTH)
    return r.status_code == 204

# ---------------------- AUDIO TOOLS ----------------------
def convert_wav_for_asterisk(src_path, dst_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", src_path,
        "-ar", "8000", "-ac", "1", "-sample_fmt", "s16",
        dst_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ---------------------- INTENT SERVICE ----------------------
import google.genai as genai

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

genai_client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.0-flash-001"

def quick_intent_check(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(hi|hello|salam|hey)\b", lower):
        return "greeting"
    if len(lower.strip()) < 3 or re.search(r"\b(hmm|uh|\.\.\.)\b", lower):
        return "unclear"
    return None

async def detect_intent(text: str) -> dict:
    prompt = (
        "You are a lead qualification assistant. Classify the transcription into one of: "
        "interested, not interested, needs follow-up, invalid number, or other. Respond with JSON: "
        "{\"intent\": <intent>, \"confidence\": <0-1>}\n\n"
        f"Transcription: \"{text}\""
    )
    from asyncio import to_thread
    response = await to_thread(lambda: genai_client.models.generate_content(
        model=MODEL_NAME, contents=[{"text": prompt}]
    ))
    content = re.sub(r"^```json|```$", "", response.text.strip())
    return json.loads(content)

# ---------------------- MAIN EVENT HANDLER ----------------------
def handle_event(event):
    if event.get("type") == "StasisStart":
        channel_id = event["channel"]["id"]
        print(f"[+] Incoming call from {event['channel'].get('caller', {}).get('number', 'unknown')}")
        api_post(f"/channels/{channel_id}/answer")
        print("[*] Call answered")
        threading.Thread(target=conversation_loop, args=(channel_id,)).start()

# ---------------------- CONVERSATION LOOP ----------------------
def conversation_loop(channel_id):
    unclear_attempts = 0
    try:
        while True:
            record_filename = f"recording-{channel_id}"
            record_path = os.path.join(RECORD_DIR, f"{record_filename}.wav")

            api_post(f"/channels/{channel_id}/record", {
                "name": record_filename,
                "format": "wav",
                "maxDurationSeconds": 5,
                "ifExists": "overwrite"
            })
            print("[*] Recording started...")
            time.sleep(6)

            if not os.path.isfile(record_path):
                print("[!] No audio recorded.")
                break

            text = asyncio.run(transcribe_audio(record_path))
            print("[STT]", text)

            if not text.strip():
                unclear_attempts += 1
                if unclear_attempts >= 2:
                    play_and_hangup(channel_id, RESPONSE_TEMPLATES["goodbye"])
                    return
                play_response(channel_id, RESPONSE_TEMPLATES["unclear"])
                continue

            quick = quick_intent_check(text)
            if quick:
                intent = {"intent": quick, "confidence": 1.0}
            else:
                intent = asyncio.run(detect_intent(text))

            print("[INTENT]", intent)
            intent_name = intent.get("intent", "other")
            response = RESPONSE_TEMPLATES.get(intent_name, RESPONSE_TEMPLATES["other"])

            print("[TEMPLATE REPLY]", response)
            play_response(channel_id, response)

            if intent_name in ["not interested", "invalid number"]:
                print("[*] Ending call due to intent:", intent_name)
                break

    except Exception as e:
        print("[!] Error in conversation loop:", e)
    finally:
        hangup_channel(channel_id)

# ---------------------- PLAYBACK ----------------------
def play_response(channel_id, text):
    tts_raw_path = generate_tts(text)
    convert_wav_for_asterisk(tts_raw_path, SOUND_FILE_PATH)
    api_post(f"/channels/{channel_id}/play", {
        "media": f"sound:ai/{SOUND_FILE_NAME}"
    })
    print("[*] Playing response...")
    time.sleep(6)

def play_and_hangup(channel_id, text):
    play_response(channel_id, text)
    hangup_channel(channel_id)

# ---------------------- CLEAN HANGUP ----------------------
def hangup_channel(channel_id):
    try:
        if api_get(f"/channels/{channel_id}"):
            print(f"[*] Hanging up channel {channel_id}")
            api_delete(f"/channels/{channel_id}")
    except requests.exceptions.HTTPError:
        print(f"[!] Channel {channel_id} already closed.")

# ---------------------- WEBSOCKET EVENTS ----------------------
def on_message(ws, message):
    handle_event(json.loads(message))

def on_error(ws, error):
    print("[ERROR]", error)

def on_close(ws, *args):
    print("[*] WebSocket closed")

def on_open(ws):
    print("[*] WebSocket connected, waiting for calls...")

# ---------------------- ENTRY POINT ----------------------
def main():
    ws = websocket.WebSocketApp(
        ARI_WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    main()
