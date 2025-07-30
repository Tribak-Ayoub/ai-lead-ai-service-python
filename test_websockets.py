import asyncio
import websockets

AUDIO_FILE = "test_audio.wav"

async def send_audio():
    uri = "ws://localhost:8000/api/whisper/ws/stream"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")

        # Read the WAV file and send it in chunks
        with open(AUDIO_FILE, "rb") as f:
            while chunk := f.read(1024):
                await websocket.send(chunk)
                await asyncio.sleep(0.01)  # simulate real-time audio

        print("Finished sending audio. Waiting for result...")

        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)  # was 3.0
            print("Received:", response)
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for transcription")
        except websockets.exceptions.ConnectionClosedOK:
            print("WebSocket connection closed.")

asyncio.run(send_audio())
