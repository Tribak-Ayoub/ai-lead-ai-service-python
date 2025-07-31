import asyncio
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from app.core.config import settings

class WhisperBufferService:
    def __init__(self):
        self.model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
        self.buffers: dict[str, bytearray] = {}
        self.lock = asyncio.Lock()
        self.on_transcript = None  # callback coroutine

    async def add_chunk(self, session_id: str, raw_pcm: bytes):
        async with self.lock:
            buf = self.buffers.setdefault(session_id, bytearray())
            buf.extend(raw_pcm)
        # threshold = sample_rate * bytes_per_sample * seconds
        thr = int(settings.sample_rate * 2 * settings.chunk_duration_s)
        if len(self.buffers[session_id]) >= thr:
            await self._transcribe(session_id)

    async def _transcribe(self, session_id: str):
        async with self.lock:
            pcm = bytes(self.buffers.pop(session_id, b""))
        # convert to float32 [-1,1]
        audio = (np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0)
        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True
            )
        )
        text = " ".join(s.text for s in segments).strip()
        if self.on_transcript:
            await self.on_transcript(session_id, text)

    async def transcribe_file(self, filepath: str) -> dict:
        data, sr = sf.read(filepath, dtype='int16')
        if sr != settings.sample_rate:
            raise RuntimeError(f"Sample rate mismatch: {sr} != {settings.sample_rate}")
        audio = data.astype(np.float32) / 32768.0
        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True
            )
        )
        text = " ".join(s.text for s in segments).strip()
        return {"text": text, "language": getattr(info, "language", "")}

    def register_callback(self, coro):
        self.on_transcript = coro

whisper_service = WhisperBufferService()
