import asyncio
import aiohttp
import base64
import json
import os
import shutil
import soundfile as sf
import resampy
import time
from pathlib import Path

from app.services.whisper_buffer_service import whisper_service
from app.services.piper_service import synthesize_with_piper
from app.core.config import settings

# === Config / constants ===
ARI_WS_URL = "ws://localhost:8088/ari/events?app=ai_lead_app"
ARI_REST_URL = os.getenv("ARI_BASE_URL", "http://localhost:8088/ari")
auth = f"{os.getenv('ARI_USERNAME', 'ai_lead_app')}:{os.getenv('ARI_PASSWORD', 'SuperSecretPass')}"
auth_header = {
    "Authorization": "Basic " + base64.b64encode(auth.encode()).decode()
}

RECORDINGS_DIR = "/var/spool/asterisk/recording"
ASTERISK_SOUNDS_CUSTOM = "/var/lib/asterisk/sounds/custom"
TEMP_COPY_DIR = "temp_recordings"
os.makedirs(TEMP_COPY_DIR, exist_ok=True)
os.makedirs(ASTERISK_SOUNDS_CUSTOM, exist_ok=True)

# Track active channels
active_channels = set()

# Playback coordination: channel_id -> asyncio.Event that is set when playback finishes
playback_done_events: dict[str, asyncio.Event] = {}


# === Helpers ===
async def play_sound(session, channel_id, media: str):
    """
    media should be like "hello-world" (built-in) or "custom/tts-<id>" (without extension).
    """
    if channel_id not in active_channels:
        print(f"[Asterisk] Skipping playback for inactive channel {channel_id}")
        return

    url = f"{ARI_REST_URL}/channels/{channel_id}/play"
    payload = {"media": f"sound:{media}"}
    async with session.post(url, headers=auth_header, json=payload) as resp:
        print(f"[Asterisk] Playback request for '{media}' returned status: {resp.status}")
        body = await resp.text()
        if resp.status >= 300:
            print(f"[Asterisk] Playback error body: {body}")
        return await resp.json() if resp.content_type == "application/json" else body


async def record_channel(session, channel_id):
    if channel_id not in active_channels:
        print(f"[Asterisk] Skipping recording for inactive channel {channel_id}")
        return

    url = f"{ARI_REST_URL}/channels/{channel_id}/record"
    payload = {
        "name": f"recording-{channel_id}",
        "format": "wav",
        "maxDurationSeconds": 3,
        "maxSilenceSeconds": 1,
        "ifExists": "overwrite",
        "beep": False
    }
    async with session.post(url, headers=auth_header, json=payload) as resp:
        print(f"[Asterisk] Start recording status: {resp.status}")
        if resp.status == 404:
            print(f"[Asterisk] Channel {channel_id} no longer exists, removing from active channels")
            active_channels.discard(channel_id)
        return await resp.json() if resp.status < 300 else None


async def hangup_channel(session, channel_id):
    """Hang up the specified channel"""
    if channel_id not in active_channels:
        print(f"[Asterisk] Channel {channel_id} not in active channels, skipping hangup")
        return

    url = f"{ARI_REST_URL}/channels/{channel_id}"
    async with session.delete(url, headers=auth_header) as resp:
        print(f"[Asterisk] Hangup request for channel {channel_id} returned status: {resp.status}")
        if resp.status < 300:
            active_channels.discard(channel_id)
        return resp.status


async def _run_qualification(channel_id, transcription):
    from app.services.intent_service import qualify_transcript
    return await qualify_transcript(channel_id, transcription)


async def handle_recording_finished(session, recording_name, channel_id):
    start_overall = time.time()
    print(f"[DEBUG] handle_recording_finished invoked for '{recording_name}' on channel {channel_id}")

    try:
        if channel_id not in active_channels:
            print(f"[DEBUG] Channel {channel_id} is not active, skipping processing.")
            return

        if not recording_name.endswith(".wav"):
            recording_name += ".wav"

        source_path = os.path.join(RECORDINGS_DIR, recording_name)
        print(f"[DEBUG] Looking for recording at: {source_path}")
        if not os.path.exists(source_path):
            print(f"[ERROR] Recording missing: {source_path}; restarting recording immediately")
            await record_channel(session, channel_id)
            return

        # Copy to temp for isolation / processing
        tmp_rec = os.path.join(TEMP_COPY_DIR, recording_name)
        try:
            shutil.copy(source_path, tmp_rec)
        except Exception as e:
            print(f"[ERROR] Copy failed: {e}; restarting recording")
            await record_channel(session, channel_id)
            return

        # Read audio and resample if needed
        try:
            data, sr = sf.read(tmp_rec)
            print(f"[DEBUG] Read audio (sr={sr}, samples={len(data)}) from {tmp_rec}")
        except Exception as e:
            print(f"[ERROR] Failed to read WAV {tmp_rec}: {e}")
            if os.path.exists(tmp_rec):
                os.remove(tmp_rec)
            await record_channel(session, channel_id)
            return

        if sr != settings.sample_rate:
            print(f"[Whisper] Resampling from {sr} to {settings.sample_rate}")
            try:
                if len(data.shape) == 1:
                    data_16k = resampy.resample(data, sr, settings.sample_rate)
                else:
                    data_16k = resampy.resample(data.T, sr, settings.sample_rate).T
                sf.write(tmp_rec, data_16k, settings.sample_rate)
                print(f"[DEBUG] Resampling completed")
            except Exception as e:
                print(f"[ERROR] Resample failed: {e}; restarting")
                if os.path.exists(tmp_rec):
                    os.remove(tmp_rec)
                await record_channel(session, channel_id)
                return
        else:
            print(f"[Whisper] Sample rate is already {sr}, no resample needed.")

        # Silence / trivial audio check
        file_size = os.path.getsize(tmp_rec)
        try:
            data_check, _ = sf.read(tmp_rec)
            max_amplitude = abs(data_check).max() if len(data_check) > 0 else 0
        except Exception:
            max_amplitude = 0
        print(f"[Whisper] Audio file size: {file_size} bytes, max amplitude: {max_amplitude}")
        if file_size < 1000 or max_amplitude < 0.01:
            print(f"[Whisper] Silent or too small audio; restarting recording")
            if os.path.exists(tmp_rec):
                os.remove(tmp_rec)
            await record_channel(session, channel_id)
            return

        # Transcribe
        t1 = time.time()
        print(f"[TIMING] Starting transcription for channel {channel_id}")
        try:
            result = await whisper_service.transcribe_file(tmp_rec)
        except Exception as e:
            print(f"[Whisper] Transcription exception: {e}")
            if os.path.exists(tmp_rec):
                os.remove(tmp_rec)
            await record_channel(session, channel_id)
            return
        transcription = result.get("text", "").strip()
        language = result.get("language", "") or settings.default_tts_lang
        print(f"[TIMING] Transcription completed in {time.time() - t1:.2f}s: '{transcription}'")
        if os.path.exists(tmp_rec):
            os.remove(tmp_rec)

        if not transcription:
            print(f"[Whisper] Empty transcription; restarting recording")
            await record_channel(session, channel_id)
            return

        # Qualification / intent
        t2 = time.time()
        qualification = await _run_qualification(channel_id, transcription)
        print(f"[TIMING] Qualification took {time.time() - t2:.2f}s: {qualification}")

        response_text = qualification.get("reply_text", "I didn't understand that. Could you repeat?")
        end_conversation = qualification.get("end", False)
        if end_conversation:
            print(f"[Conversation] Ending call for channel {channel_id} based on intent.")
            return

        # TTS synthesis
        t3 = time.time()
        try:
            loop = asyncio.get_running_loop()
            tts_temp = await loop.run_in_executor(
                None,
                lambda: synthesize_with_piper(response_text, lang="en", sample_rate=8000)
            )
            print(f"[TIMING] TTS synthesis finished in {time.time() - t3:.2f}s, file: {tts_temp}")
        except Exception as e:
            print(f"[TTS] Piper generation failed: {e}; restarting recording")
            await record_channel(session, channel_id)
            return

        # Prepare TTS file for Asterisk (detect extension .ulaw or .wav)
        tts_path_obj = Path(tts_temp)
        ext = tts_path_obj.suffix  # .ulaw or .wav
        dest_basename = f"tts-{channel_id}{ext}"
        dest_tts_path = os.path.join(ASTERISK_SOUNDS_CUSTOM, dest_basename)
        try:
            shutil.copy(tts_temp, dest_tts_path)
            print(f"[TTS] Copied TTS file to {dest_tts_path}")
            if os.path.exists(tts_temp):
                os.remove(tts_temp)
            try:
                os.chown(dest_tts_path, os.getuid(), os.getgid())
            except Exception:
                pass
            os.chmod(dest_tts_path, 0o644)
        except Exception as e:
            print(f"[ERROR] TTS file handling failed: {e}; restarting recording")
            await record_channel(session, channel_id)
            return

        # Setup playback completion event
        playback_done = asyncio.Event()
        playback_done_events[channel_id] = playback_done

        # Playback TTS (without extension, Asterisk will pick appropriate file)
        sound_ref = f"custom/tts-{channel_id}"
        print(f"[DEBUG] Initiating playback of '{sound_ref}' on channel {channel_id}")
        _ = asyncio.create_task(play_sound(session, channel_id, sound_ref))

        # WAIT for playback to finish, but bound it so we don’t hang forever.
        # This await only pauses this call’s continuation; it does not block the event loop or other channels.
        try:
            await asyncio.wait_for(playback_done.wait(), timeout=5.0)
            print(f"[TIMING] Playback finished for channel {channel_id} (event received)")
        except asyncio.TimeoutError:
            print(f"[WARNING] PlaybackFinished event did not arrive within timeout for channel {channel_id}, proceeding anyway.")

        # Clean up event so next cycle creates fresh one
        if channel_id in playback_done_events:
            del playback_done_events[channel_id]

        # Immediately start next recording
        await record_channel(session, channel_id)
        print(f"[TIMING] Total cycle time: {time.time() - start_overall:.2f}s for channel {channel_id}")

    except Exception as e:
        print(f"[ERROR] Unexpected error in handle_recording_finished: {e}")
        try:
            await record_channel(session, channel_id)
        except Exception as e2:
            print(f"[ERROR] Failed to restart recording after error: {e2}")


# === Main loop ===
async def main():
    print("[*] Starting ARI WebSocket client...")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ARI_WS_URL, headers=auth_header) as ws:
            print("[*] Connected to ARI WebSocket")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    event_type = data.get("type")
                    print(f"[Event] {event_type} raw: {json.dumps(data)}")

                    if event_type == "StasisStart":
                        channel_id = data["channel"]["id"]
                        print(f"[Call] Started on channel {channel_id}")
                        active_channels.add(channel_id)
                        await play_sound(session, channel_id, "hello-world")
                        await play_sound(session, channel_id, "beep")
                        await record_channel(session, channel_id)

                    elif event_type == "StasisEnd":
                        channel_id = data.get("channel", {}).get("id")
                        if channel_id:
                            print(f"[Call] Ended on channel {channel_id}")
                            active_channels.discard(channel_id)

                    elif event_type == "ChannelDestroyed":
                        channel_id = data.get("channel", {}).get("id")
                        if channel_id:
                            print(f"[Call] Channel destroyed: {channel_id}")
                            active_channels.discard(channel_id)

                    elif event_type == "RecordingFinished":
                        try:
                            recording_name = data.get("recording", {}).get("name")
                            channel_id = data.get("channel", {}).get("id")
                            if not channel_id:
                                target_uri = data.get("recording", {}).get("target_uri", "")
                                if target_uri.startswith("channel:"):
                                    channel_id = target_uri.replace("channel:", "")

                            print(f"[DEBUG] RecordingFinished - recording_name: {recording_name}, channel_id: {channel_id}")
                            if recording_name and channel_id:
                                await handle_recording_finished(session, recording_name, channel_id)
                            else:
                                print(f"[ERROR] Missing recording_name or channel_id in RecordingFinished event")
                                print(f"[ERROR] Full event data: {json.dumps(data)}")
                        except Exception as e:
                            print(f"[ERROR] Exception in RecordingFinished handler: {e}")
                            import traceback
                            traceback.print_exc()

                    elif event_type == "PlaybackStarted":
                        print(f"[ARI] PlaybackStarted: {json.dumps(data)}")

                    elif event_type == "PlaybackFinished":
                        print(f"[ARI] PlaybackFinished: {json.dumps(data)}")
                        playback = data.get("playback", {})
                        target_uri = playback.get("target_uri", "")
                        channel_id = None

                        if isinstance(target_uri, str) and target_uri.startswith("channel:"):
                            channel_id = target_uri.replace("channel:", "")
                        else:
                            channel_id = data.get("channel", {}).get("id")

                        if not channel_id:
                            print(f"[WARNING] Could not determine channel_id from PlaybackFinished event: {data}")
                        else:
                            if channel_id in playback_done_events:
                                playback_done_events[channel_id].set()
                            else:
                                print(f"[DEBUG] No playback event waiting for channel {channel_id}")

                    else:
                        pass

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"[WebSocket] Error: {msg.data}")
                    break


if __name__ == "__main__":
    asyncio.run(main())
