import asyncio
import json
import base64
from typing import Callable
import httpx
import websockets
import os

ARI_USER = os.getenv("ARI_USERNAME", "aiuser")
ARI_PASS = os.getenv("ARI_PASSWORD", "SuperSecretPass")
ARI_BASE = os.getenv("ARI_BASE_URL", "http://localhost:8088/ari")
STASIS_APP = "ai_lead_app"

class ARIController:
    def __init__(self, session_id: str, channel_id: str):
        self.session_id = session_id
        self.channel_id = channel_id
        self.bridge_id = None
        self.ws_events = None
        self.audio_send_queue = asyncio.Queue()

    async def attach_to_stasis(self):
        async with httpx.AsyncClient(auth=(ARI_USER, ARI_PASS)) as client:
            r = await client.post(f"{ARI_BASE}/bridges", params={"type": "mixing"})
            data = r.json()
            self.bridge_id = data["id"]

            await client.post(f"{ARI_BASE}/bridges/{self.bridge_id}/addChannel", json={"channel": self.channel_id})

            ws_url = f"ws://localhost:8088/ari/events?api_key={ARI_USER}:{ARI_PASS}&app={STASIS_APP}"
            self.ws_events = await websockets.connect(ws_url)
            asyncio.create_task(self._event_listener())

    async def _event_listener(self):
        async for msg in self.ws_events:
            event = json.loads(msg)
            print(f"[ARI EVENT] {event.get('type')}")

    async def play_tts(self, wav_bytes: bytes):
        fname = f"/tmp/tts_{self.session_id}.wav"
        with open(fname, "wb") as f:
            f.write(wav_bytes)

        async with httpx.AsyncClient(auth=(ARI_USER, ARI_PASS)) as client:
            await client.post(f"{ARI_BASE}/channels/{self.channel_id}/play", json={
                "media": f"sound:tts_{self.session_id}"
            })

    async def send_audio_to_pipeline(self, raw_pcm_bytes: bytes, on_reply: Callable[[str], None]):
        # Implementation placeholder for pipeline integration
        pass
