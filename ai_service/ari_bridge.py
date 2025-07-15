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

os.makedirs(SOUNDS_DIR, exist_ok=True)

# ───── Text to Speech (TTS) function ─────
def text_to_speech(text, filepath):
    """Generate a WAV file from text using espeak + sox"""
    speak = subprocess.Popen(["espeak", "-s", "130", "--stdout", text], stdout=subprocess.PIPE)
    subprocess.run(["sox", "-t", "wav", "-", "-r", "8000", "-c", "1", "-b", "16", filepath],
                   stdin=speak.stdout, check=True)
    speak.stdout.close()

# ───── Handle incoming call ─────
async def handle_call(chan_id: str, pb_id: str, future: asyncio.Future):
    print(f"\n📞 Handling call {chan_id}")
    requests.post(f"{ARI_REST_URL}/channels/{chan_id}/answer", auth=AUTH)

    ai_response = "Hello tribak! How can I help you today?"
    wav_file = f"{SOUNDS_DIR}/tts-{chan_id}.wav"
    text_to_speech(ai_response, wav_file)

    requests.post(f"{ARI_REST_URL}/channels/{chan_id}/play", auth=AUTH, json={
        "media": f"sound:custom/tts-{chan_id}",
        "playbackId": pb_id
    })
    print(f"▶️ Playing: {ai_response} (playbackId: {pb_id})")

    await future  # wait for PlaybackFinished
    requests.delete(f"{ARI_REST_URL}/channels/{chan_id}", auth=AUTH)
    print(f"📴 Call {chan_id} hung up")

# ───── Main WebSocket loop ─────
async def main():
    futures = {}  # pb_id -> asyncio.Future
    print(f"Connecting to {ARI_WS_URL} ...")

    async with websockets.connect(ARI_WS_URL) as ws:
        print("✅ Connected to ARI WebSocket, waiting for calls ...")

        async for message in ws:
            event = json.loads(message)

            # ── Handle new call ──
            if event.get("type") == "StasisStart":
                chan_id = event["channel"]["id"]
                pb_id = f"pb-{chan_id}"
                fut = asyncio.get_event_loop().create_future()
                futures[pb_id] = fut
                asyncio.create_task(handle_call(chan_id, pb_id, fut))

            # ── Handle playback finished ──
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
