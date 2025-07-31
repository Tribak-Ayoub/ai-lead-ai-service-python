# test_audio_ws_client.py
import asyncio
import websockets
import wave

async def send_wav_as_stream(wav_file):
    uri = "ws://localhost:8000/ws/audio"

    async with websockets.connect(uri) as ws:
        wf = wave.open(wav_file, 'rb')
        chunk_size = 320  # for 8000Hz, 16-bit, mono, ~20ms
        chunk = wf.readframes(chunk_size)

        while chunk:
            await ws.send(chunk)
            await asyncio.sleep(0.02)  # simulate real-time
            chunk = wf.readframes(chunk_size)

        print("Done sending audio")

asyncio.run(send_wav_as_stream("test.wav"))
