import asyncio
import numpy as np
from faster_whisper import WhisperModel
from app.core.config import settings
import soundfile as sf

class WhisperBufferService:
    def __init__(self):
        self.model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
        self.buffers = {}  # session_id -> bytearray
        self.lock = asyncio.Lock()
        self.on_transcript = None  # callback coroutine

    async def add_chunk(self, session_id: str, raw_pcm: bytes):
        async with self.lock:
            buf = self.buffers.setdefault(session_id, bytearray())
            buf.extend(raw_pcm)

        bytes_per_second = settings.sample_rate * 2  # 16-bit audio (2 bytes)
        threshold = int(bytes_per_second * settings.chunk_duration_s)
        if len(self.buffers[session_id]) >= threshold:
            await self._transcribe(session_id)

    async def _transcribe(self, session_id: str):
        async with self.lock:
            pcm = bytes(self.buffers[session_id])
            self.buffers[session_id].clear()

        audio_array = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(None, lambda: self.model.transcribe(
            audio_array,
            beam_size=5,
            language="en",
            vad_filter=True
        ))

        text = " ".join(segment.text for segment in segments).strip()

        if self.on_transcript:
            await self.on_transcript(session_id, text)

    def register_callback(self, coro):
        self.on_transcript = coro

    async def transcribe_file(self, filepath: str):
        data, samplerate = sf.read(filepath, dtype='int16')
        if samplerate != settings.sample_rate:
            print(f"[Whisper] File sample rate: {samplerate}, expected: {settings.sample_rate}")
            # Don't raise error, just log the difference
            
        audio_array = data.astype(np.float32) / 32768.0
        
        # Check if audio has sufficient content
        max_amplitude = np.abs(audio_array).max()
        print(f"[Whisper] Audio max amplitude: {max_amplitude}")
        
        if max_amplitude < 0.01:
            print(f"[Whisper] Audio appears to be too quiet (max amplitude: {max_amplitude})")
            return {"text": "", "language": "en"}

        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(None, lambda: self.model.transcribe(
            audio_array,
            beam_size=5,
            language="en",
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,  # Shorter silence duration
                threshold=0.3,                 # Lower threshold for speech detection
            ),
            initial_prompt="This is a phone conversation about business solutions, budget, and demos.",
        ))

        text = " ".join(segment.text for segment in segments).strip()
        language = info.language if hasattr(info, "language") else "en"
        
        print(f"[Whisper] Raw segments: {[(s.start, s.end, s.text) for s in segments]}")
        print(f"[Whisper] Final transcription: '{text}'")

        return {"text": text, "language": language}

whisper_service = WhisperBufferService()