import asyncio
import aiohttp
import base64
import json
import os
import shutil
import soundfile as sf
import resampy

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


# === Helpers ===
async def play_sound(session, channel_id, media: str):
    """
    media should be like "hello-world" (built-in) or "custom/tts-<id>" (without .wav).
    """
    url = f"{ARI_REST_URL}/channels/{channel_id}/play"
    payload = {"media": f"sound:{media}"}
    async with session.post(url, headers=auth_header, json=payload) as resp:
        print(f"[Asterisk] Playback request for '{media}' returned status: {resp.status}")
        body = await resp.text()
        if resp.status >= 300:
            print(f"[Asterisk] Playback error body: {body}")
        return await resp.json() if resp.content_type == "application/json" else body


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


async def handle_recording_finished(session, recording_name, channel_id):
    print(f"[DEBUG] handle_recording_finished invoked for '{recording_name}' on channel {channel_id}")
    
    try:
        # Normalize name
        if not recording_name.endswith(".wav"):
            recording_name += ".wav"

        source_path = os.path.join(RECORDINGS_DIR, recording_name)
        print(f"[DEBUG] Looking for recording at: {source_path}")
        print(f"[DEBUG] RECORDINGS_DIR exists: {os.path.exists(RECORDINGS_DIR)}")
        
        if os.path.exists(RECORDINGS_DIR):
            available_files = os.listdir(RECORDINGS_DIR)
            print(f"[DEBUG] Available files in recordings dir: {available_files}")
        
        if not os.path.exists(source_path):
            print(f"[ERROR] Recording not found at expected path: {source_path}")
            # Even if recording failed, continue the conversation loop
            await record_channel(session, channel_id)
            return

        # Copy to temp for processing
        tmp_rec = os.path.join(TEMP_COPY_DIR, recording_name)
        try:
            print(f"[DEBUG] Copying {source_path} to {tmp_rec}")
            shutil.copy(source_path, tmp_rec)
            print(f"[DEBUG] Copy successful")
        except Exception as e:
            print(f"[ERROR] Failed to copy recording: {e}")
            await record_channel(session, channel_id)
            return

        # Ensure sample rate is what Whisper expects (16000)
        try:
            print(f"[DEBUG] Reading audio file: {tmp_rec}")
            data, sr = sf.read(tmp_rec)
            print(f"[DEBUG] Audio file read successfully - sample rate: {sr}, length: {len(data)}")
        except Exception as e:
            print(f"[ERROR] Failed to read WAV {tmp_rec}: {e}")
            if os.path.exists(tmp_rec):
                os.remove(tmp_rec)
            await record_channel(session, channel_id)
            return

        if sr != settings.sample_rate:
            print(f"[Whisper] Resampling from {sr} to {settings.sample_rate}")
            try:
                data_16k = resampy.resample(data.T, sr, settings.sample_rate).T
                sf.write(tmp_rec, data_16k, settings.sample_rate)
                print(f"[DEBUG] Resampling completed")
            except Exception as e:
                print(f"[ERROR] Failed to resample: {e}")
                if os.path.exists(tmp_rec):
                    os.remove(tmp_rec)
                await record_channel(session, channel_id)
                return
        else:
            print(f"[Whisper] Sample rate is already {sr}, no resample needed.")

        # Transcribe
        print(f"[Whisper] Transcribing {tmp_rec}")
        try:
            result = await whisper_service.transcribe_file(tmp_rec)
            print(f"[DEBUG] Transcription completed: {result}")
        except Exception as e:
            print(f"[Whisper] Transcription failed: {e}")
            import traceback
            traceback.print_exc()
            if os.path.exists(tmp_rec):
                os.remove(tmp_rec)
            await record_channel(session, channel_id)
            return

        transcription = result.get("text", "").strip()
        language = result.get("language", "") or settings.default_tts_lang
        print(f"[Whisper] transcription: '{transcription}' (lang={language})")
        
        if os.path.exists(tmp_rec):
            os.remove(tmp_rec)

        if not transcription:
            print("[Whisper] Empty transcription; starting new recording.")
            await record_channel(session, channel_id)
            return

        # Process the transcription through your qualification system
        try:
            print(f"[DEBUG] Processing qualification for: {transcription}")
            from app.services.intent_service import qualify_transcript
            qualification = await qualify_transcript(channel_id, transcription)
            print(f"[Qualification] Result: {qualification}")
            
            # Check if conversation should end
            if qualification.get("end", False):
                print(f"[Conversation] Ending call for channel {channel_id}")
                # You might want to add hangup logic here
                return
                
            response_text = qualification.get("reply_text", "I didn't understand that. Could you repeat?")
        except Exception as e:
            print(f"[ERROR] Qualification failed: {e}")
            import traceback
            traceback.print_exc()
            response_text = "I'm sorry, I didn't catch that. Could you repeat?"

        # Generate TTS
        try:
            print(f"[TTS] Synthesizing speech for text: {response_text}")
            tts_temp = synthesize_with_piper(response_text, lang="en", sample_rate=8000)
            print(f"[TTS] Synthesized temp file: {tts_temp}")
        except Exception as e:
            print(f"[TTS] Piper generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue conversation even if TTS fails
            await record_channel(session, channel_id)
            return

        # Copy into Asterisk sounds folder with stable name
        tts_basename = f"tts-{channel_id}.wav"
        dest_tts_path = os.path.join(ASTERISK_SOUNDS_CUSTOM, tts_basename)
        print(f"[TTS] Copying to Asterisk sounds folder: {dest_tts_path}")
        try:
            # TTS should already be at 8000 Hz, just copy
            shutil.copy(tts_temp, dest_tts_path)
            print(f"[TTS] Copied TTS WAV to {dest_tts_path}")
            print(f"[TTS] File exists after copy? {os.path.exists(dest_tts_path)}")
            print(f"[TTS] File size: {os.path.getsize(dest_tts_path)} bytes")

            # Verify sample rate
            try:
                verify_data, verify_sr = sf.read(dest_tts_path)
                print(f"[TTS] Verified sample rate: {verify_sr} Hz")
            except Exception as verify_e:
                print(f"[TTS] Could not verify sample rate: {verify_e}")

            os.remove(tts_temp)

            # Ensure permissions so Asterisk can read it
            try:
                os.chown(dest_tts_path, os.getuid(), os.getgid())
            except Exception:
                pass
            os.chmod(dest_tts_path, 0o644)

            # Playback TTS (drop '.wav')
            sound_ref = f"custom/tts-{channel_id}"
            print(f"[DEBUG] Playing back TTS '{sound_ref}' on channel {channel_id}")
            await play_sound(session, channel_id, sound_ref)
            
        except Exception as e:
            print(f"[ERROR] TTS file handling failed: {e}")
            import traceback
            traceback.print_exc()
        
        # CRITICAL: Start a new recording to continue the conversation
        print(f"[DEBUG] Starting new recording cycle for channel {channel_id}")
        await record_channel(session, channel_id)
        
    except Exception as e:
        print(f"[ERROR] Unexpected error in handle_recording_finished: {e}")
        import traceback
        traceback.print_exc()
        # Try to continue conversation even if there was an error
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
                        await play_sound(session, channel_id, "hello-world")
                        await play_sound(session, channel_id, "beep")
                        await record_channel(session, channel_id)

                    elif event_type == "RecordingFinished":
                        try:
                            recording_name = data.get("recording", {}).get("name")
                            channel_id = data.get("channel", {}).get("id")
                            
                            # If channel_id is not directly available, extract from target_uri
                            if not channel_id:
                                target_uri = data.get("recording", {}).get("target_uri", "")
                                if target_uri.startswith("channel:"):
                                    channel_id = target_uri.replace("channel:", "")
                            
                            print(f"[DEBUG] RecordingFinished - recording_name: {recording_name}, channel_id: {channel_id}")
                            if recording_name and channel_id:
                                print(f"[DEBUG] Calling handle_recording_finished...")
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

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"[WebSocket] Error: {msg.data}")
                    break


if __name__ == "__main__":
    asyncio.run(main())