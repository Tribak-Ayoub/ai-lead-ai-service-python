import os
import wave
import tempfile
from faster_whisper import WhisperModel

# Load Whisper medium model once at import
model = WhisperModel("base")

def save_raw_pcm_to_wav(buffer: bytes, sample_rate=8000, sample_width=2, channels=1) -> str:
    """
    Save raw PCM bytes to a valid WAV file and return the file path.
    Assumes 16-bit PCM, mono, 8kHz by default (adjust if needed).
    """
    tmpfile = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmpfile.name, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)  # 2 bytes = 16 bits
        wf.setframerate(sample_rate)
        wf.writeframes(buffer)
    return tmpfile.name

async def transcribe_buffered_audio(buffer: bytes) -> dict:
    """
    Save raw audio buffer as WAV, transcribe it using Whisper,
    then delete temp file and return transcription and language.
    """
    wav_path = save_raw_pcm_to_wav(buffer)
    print(f"Transcribing {len(buffer)} bytes of audio...")

    try:
        segments, info = model.transcribe(wav_path)
        transcription = " ".join([segment.text for segment in segments])
        detected_lang = info.language
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
    return {"text": transcription, "language": detected_lang}
