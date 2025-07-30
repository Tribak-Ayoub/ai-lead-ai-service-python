import asyncio
import websockets
import soundfile as sf
import aiohttp
import base64
import json
from tempfile import NamedTemporaryFile

WHISPER_STT_URL = "http://localhost:8000/stt"  # Adjust if different
SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 500  # 0.5 seconds of audio
BYTES_PER_SECOND = SAMPLE_RATE * 2
CHUNK_SIZE = int((CHUNK_DURATION_MS / 1000) * BYTES_PER_SECOND)

async def stream_audio_to_whisper(audio_buffer):
    """Send the audio to STT (Whisper or FastAPI) and return text."""
    with NamedTemporaryFile(delete=True, suffix=".wav") as tmp:
        sf.write(tmp.name, audio_buffer, SAMPLE_RATE, format="WAV")
        async with aiohttp.ClientSession() as session:
            with open(tmp.name, "rb") as f:
                files = {"file": f}
                async with session.post(WHISPER_STT_URL, data=files) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("text", "")
                    else:
                        print("STT request failed:", resp.status)
                        return ""

async def handle_external_media_ws(uri):
    """Connect to Asterisk externalMedia WebSocket stream (raw audio)."""
    async with websockets.connect(uri) as ws:
        audio_buffer = b""
        while True:
            try:
                frame = await ws.recv()
                if isinstance(frame, bytes):
                    audio_buffer += frame

                    # Once we have enough audio, process it
                    if len(audio_buffer) >= CHUNK_SIZE:
                        print("[INFO] Processing audio chunk...")
                        audio_data = sf.frombuffer(audio_buffer, dtype='int16')
                        text = await stream_audio_to_whisper(audio_data)
                        print("[STT Result]", text)

                        # Clear buffer after processing
                        audio_buffer = b""
                else:
                    print("[WARN] Received non-bytes frame:", frame)
            except websockets.ConnectionClosed:
                print("[INFO] WebSocket connection closed")
                break
