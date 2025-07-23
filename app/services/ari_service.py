import requests
import threading
import websocket
import json
import time
import os
import asyncio

from app.services.whisper_service import transcribe_audio
from app.services.intent_service import detect_intent
from app.services.piper_service import synthesize_with_piper as generate_tts

import subprocess

def convert_wav_for_asterisk(src_path, dst_path):
    subprocess.run([
        'ffmpeg',
        '-y',                   # overwrite existing file
        '-i', src_path,         # input TTS file
        '-ar', '8000',          # 8000 Hz (required by Asterisk for ulaw)
        '-ac', '1',             # mono
        '-sample_fmt', 's16',   # 16-bit signed PCM
        dst_path
    ])

# Configuration
ARI_URL = "http://localhost:8088/ari"
ARI_WS_URL = "ws://localhost:8088/ari/events?api_key=aiuser:SuperSecretPass&app=ai-assistant"
APP_NAME = "ai-assistant"
AUTH = ("aiuser", "SuperSecretPass")

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

def handle_event(event):
    if event.get("type") == "StasisStart":
        channel = event["channel"]
        channel_id = channel["id"]
        caller_num = channel.get("caller", {}).get("number", "unknown")
        print(f"[+] Incoming call from {caller_num}")

        # Answer call
        api_post(f"/channels/{channel_id}/answer")
        print("[*] Call answered")

        # Start recording
        record_filename = f"recording-{channel_id}"
        record_path = f"/var/spool/asterisk/recording/{record_filename}.wav"
        api_post(f"/channels/{channel_id}/record", {
           "name": record_filename,
           "format": "wav",
           "maxDurationSeconds": 5,
           "ifExists": "overwrite"
        })
        print("[*] Recording started")

        # Wait for recording and respond
        threading.Thread(target=wait_for_recording, args=(channel_id, record_path)).start()

def wait_for_recording(channel_id, record_path):
    print("[*] Waiting for recording to finish...")
    time.sleep(6)

    if not os.path.isfile(record_path):
        print("[!] Recording not found:", record_path)
        return

    print("[*] Recording finished:", record_path)

    # Transcribe and detect intent
    text = asyncio.run(transcribe_audio(record_path))
    print("[STT]", text)
    intent = asyncio.run(detect_intent(text))
    print("[INTENT]", intent)

    # Generate TTS and convert format
    response_text = f"{intent['intent']} with confidence {intent['confidence']:.2f}"
    tts_path_raw = generate_tts(response_text)
    print("[TTS] Generated raw:", tts_path_raw)

    tts_path = "/tmp/converted.wav"
    os.system(f"ffmpeg -y -i {tts_path_raw} -ar 16000 -ac 1 -c:a pcm_s16le {tts_path}")
    print("[TTS] Converted to:", tts_path)

    # Copy to Asterisk sounds folder
    sound_file_name = "ai_response"
    sound_file_path = f"/var/lib/asterisk/sounds/ai/{sound_file_name}.wav"
    convert_wav_for_asterisk(tts_path_raw, sound_file_path)
    print("[TTS] Converted and copied to:", sound_file_path)


    # Play TTS on channel
    api_post(f"/channels/{channel_id}/play", {
        "media": f"sound:ai/{sound_file_name}"
    })
    print("[*] Playing TTS to caller")

    # Wait long enough for playback to finish before hangup
    time.sleep(7)

    # Hangup channel safely
    hangup_channel(channel_id)

def hangup_channel(channel_id):
    try:
        res = api_get(f"/channels/{channel_id}")
        if res:
            print(f"[*] Hanging up channel {channel_id}")
            api_delete(f"/channels/{channel_id}")
    except requests.exceptions.HTTPError:
        print(f"[!] Channel {channel_id} already closed, cannot hang up.")

# WebSocket Callbacks
def on_message(ws, message):
    event = json.loads(message)
    handle_event(event)

def on_error(ws, error):
    print("[ERROR]", error)

def on_close(ws, close_status_code, close_msg):
    print("[*] WebSocket closed")

def on_open(ws):
    print("[*] WebSocket connected, waiting for calls...")

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
