import asyncio
import aiohttp
import base64
import json
import os
import shutil

from app.services.whisper_service import transcribe_audio

ARI_WS_URL = "ws://localhost:8088/ari/events?app=ai-assistant"
ARI_REST_URL = "http://localhost:8088/ari"
auth = "aiuser:SuperSecretPass"
auth_header = {
    "Authorization": "Basic " + base64.b64encode(auth.encode()).decode()
}

RECORDINGS_DIR = "/var/spool/asterisk/recordings"  # or wherever Asterisk saves them
TEMP_COPY_DIR = "temp_recordings"
os.makedirs(TEMP_COPY_DIR, exist_ok=True)

async def play_sound(session, channel_id, sound="hello-world"):
    url = f"{ARI_REST_URL}/channels/{channel_id}/play"
    payload = {
        "media": f"sound:{sound}"
    }
    async with session.post(url, headers=auth_header, json=payload) as resp:
        print(f"[Asterisk] Playback status: {resp.status}")
        return await resp.json()

async def record_channel(session, channel_id):
    url = f"{ARI_REST_URL}/channels/{channel_id}/record"
    payload = {
        "name": f"recording-{channel_id}",
        "format": "wav",
        "maxDurationSeconds": 10,
        "maxSilenceSeconds": 3,
        "ifExists": "overwrite",
        "beep": True
    }
    async with session.post(url, headers=auth_header, json=payload) as resp:
        print(f"[Asterisk] Start recording status: {resp.status}")
        return await resp.json()

async def handle_recording_finished(recording_name):
    source_path = f"/var/spool/asterisk/recording-{recording_name}.wav"
    if not os.path.exists(source_path):
        print(f"[Whisper] Recording not found: {source_path}")
        return

    dest_path = os.path.join(TEMP_COPY_DIR, f"{recording_name}.wav")
    shutil.copy(source_path, dest_path)

    print(f"[Whisper] Transcribing {dest_path}")
    result = await transcribe_audio(dest_path)
    print(f"[Whisper] → Transcription: {result['text']}")
    print(f"[Whisper] → Language: {result['language']}")

    os.remove(dest_path)

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ARI_WS_URL, headers=auth_header) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    event_type = data.get("type")
                    print(f"[Event] {event_type}")

                    if event_type == "StasisStart":
                        channel_id = data["channel"]["id"]
                        print(f"[Call] Started on channel {channel_id}")
                        await play_sound(session, channel_id, "hello-world")
                        await record_channel(session, channel_id)

                    elif event_type == "RecordingFinished":
                        recording_name = data.get("recording", {}).get("name")
                        if recording_name:
                            await handle_recording_finished(recording_name)

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

asyncio.run(main())
