# import os
# import wave
# import tempfile
# from faster_whisper import WhisperModel

# # Load Whisper model once
# model = WhisperModel("base")

# def transcribe_wav_file(wav_path: str) -> str:
#     segments, _ = model.transcribe(wav_path)
#     result = " ".join([seg.text.strip() for seg in segments])
#     return result

# def save_raw_pcm_to_wav(buffer: bytes, sample_rate=8000, sample_width=2, channels=1) -> str:
#     tmpfile = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
#     with wave.open(tmpfile.name, 'wb') as wf:
#         wf.setnchannels(channels)
#         wf.setsampwidth(sample_width)
#         wf.setframerate(sample_rate)
#         wf.writeframes(buffer)
#     return tmpfile.name

# async def transcribe_buffered_audio(buffer: bytes) -> dict:
#     wav_path = save_raw_pcm_to_wav(buffer)
#     print(f"Transcribing {len(buffer)} bytes of audio...")

#     try:
#         segments, info = model.transcribe(wav_path)
#         transcription = " ".join([segment.text for segment in segments])
#         detected_lang = info.language
#     finally:
#         if os.path.exists(wav_path):
#             os.remove(wav_path)
#     return {"text": transcription, "language": detected_lang}
