#!/usr/bin/env python3

import asyncio, json, os, subprocess
import websockets, requests
from requests.auth import HTTPBasicAuth

# ───── Configuration ─────
ARI_USER = "aiuser"
ARI_PASS = "SuperSecretPass"
ARI_IP = "127.0.0.1"
ARI_APP = "ai-assistant"
ARI_WS_URL = f"ws://{ARI_IP}:8088/ari/events?api_key={ARI_USER}:{ARI_PASS}&app={ARI_APP}"
ARI_REST_URL = f"http://{ARI_IP}:8088/ari"
SOUNDS_DIR = "/var/lib/asterisk/sounds/custom"
AUTH = HTTPBasicAuth(ARI_USER, ARI_PASS)

# Create sounds directory if missing
os.makedirs(SOUNDS_DIR, exist_ok=True)

# ───── Text to Speech using Piper ─────
def text_to_speech(text, wav_path_raw, wav_path_final):
    """Generate TTS audio using Piper and convert to Asterisk-compatible format"""
    from services.tts import synthesize_text

    print(f"🧠 Synthesizing: '{text}'")
    synthesize_text(text, wav_path_raw)

    # Convert to 8000Hz mono WAV (required by Asterisk)
    subprocess.run([
        "sox", wav_path_raw, "-r", "8000", "-c", "1", "-b", "16", wav_path_final
    ], check=True)

# ───── Handle incoming call ─────
async def handle_call(chan_id: str, pb_id: str, future: asyncio.Future):
    print(f"\n📞 Handling call {chan_id}")

    # Answer the call
    requests.post(f"{ARI_REST_URL}/channels/{chan_id}/answer", auth=AUTH)

    # Generate AI response
    ai_response = "مرحبا! كيف يمكنني مساعدتك اليوم؟"
    raw_path = f"/tmp/tts-{chan_id}-raw.wav"
    final_path = f"{SOUNDS_DIR}/tts-{chan_id}.wav"
    text_to_speech(ai_response, raw_path, final_path)

    # Play the audio
    requests.post(f"{ARI_REST_URL}/channels/{chan_id}/play", auth=AUTH, json={
        "media": f"sound:custom/tts-{chan_id}",
        "playbackId": pb_id
    })
    print(f"▶️ Playing: {ai_response} (playbackId: {pb_id})")

    # Wait for playback to finish
    await future

    # Hang up
    requests.delete(f"{ARI_REST_URL}/channels/{chan_id}", auth=AUTH)
    print(f"📴 Call {chan_id} hung up")

# ───── Main WebSocket loop ─────
async def main():
    futures = {}  # pb_id -> asyncio.Future
    print(f"Connecting to {ARI_WS_URL} ...")

    async with websockets.connect(ARI_WS_URL) as ws:
        print("✅ Connected to ARI WebSocket. Waiting for calls...")

        async for message in ws:
            event = json.loads(message)

            if event.get("type") == "StasisStart":
                chan_id = event["channel"]["id"]
                pb_id = f"pb-{chan_id}"
                fut = asyncio.get_event_loop().create_future()
                futures[pb_id] = fut
                asyncio.create_task(handle_call(chan_id, pb_id, fut))

            elif event.get("type") == "PlaybackFinished":
                pb_id = event["playback"]["id"]
                if pb_id in futures:
                    futures[pb_id].set_result(True)
                    del futures[pb_id]

# ───── Entry point ─────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔌 Exiting ...")
