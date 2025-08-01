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
            beam_size=2,
            language="en",
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,  # Shorter silence duration
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




# import asyncio
# import numpy as np
# from faster_whisper import WhisperModel
# from app.core.config import settings
# import soundfile as sf
# import time

# class WhisperBufferService:
#     def __init__(self):
#         # Use smaller model for faster processing
#         model_size = getattr(settings, 'whisper_model_size', 'base')  # base is faster than large
#         self.model = WhisperModel(
#             model_size, 
#             device="cpu", 
#             compute_type="int8",
#             num_workers=2  # Parallel processing
#         )
#         self.buffers = {}  # session_id -> bytearray
#         self.lock = asyncio.Lock()
#         self.on_transcript = None  # callback coroutine
#         self.last_transcription_time = {}  # Track timing for optimization

#     async def add_chunk(self, session_id: str, raw_pcm: bytes):
#         async with self.lock:
#             buf = self.buffers.setdefault(session_id, bytearray())
#             buf.extend(raw_pcm)

#         bytes_per_second = settings.sample_rate * 2  # 16-bit audio (2 bytes)
#         # Reduce chunk duration for faster response (1.5s instead of longer)
#         chunk_duration = getattr(settings, 'chunk_duration_s', 1.5)
#         threshold = int(bytes_per_second * chunk_duration)
        
#         if len(self.buffers[session_id]) >= threshold:
#             await self._transcribe(session_id)

#     async def _transcribe(self, session_id: str):
#         start_time = time.time()
        
#         async with self.lock:
#             pcm = bytes(self.buffers[session_id])
#             self.buffers[session_id].clear()

#         # Skip if audio is too short (less than 0.5 seconds)
#         min_audio_length = settings.sample_rate * 2 * 0.5  # 0.5 seconds
#         if len(pcm) < min_audio_length:
#             print(f"[Whisper] Skipping transcription - audio too short ({len(pcm)} bytes)")
#             return

#         audio_array = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        
#         # Check for silence before processing
#         max_amplitude = np.abs(audio_array).max()
#         if max_amplitude < 0.02:  # Slightly higher threshold for real-time
#             print(f"[Whisper] Skipping silent audio (max amplitude: {max_amplitude})")
#             return

#         loop = asyncio.get_running_loop()
        
#         # Optimized transcription parameters for speed
#         segments, info = await loop.run_in_executor(None, lambda: self.model.transcribe(
#             audio_array,
#             beam_size=1,  # Reduced from 5 for speed
#             language="en",
#             vad_filter=True,
#             vad_parameters=dict(
#                 min_silence_duration_ms=300,  # Even shorter for responsiveness
#                 threshold=0.4,  # Slightly higher threshold
#             ),
#             # Shorter initial prompt for faster processing
#             initial_prompt="Phone sales call.",
#             without_timestamps=True,  # Skip timestamps for speed
#         ))

#         text = " ".join(segment.text for segment in segments).strip()
        
#         processing_time = time.time() - start_time
#         print(f"[Whisper] Transcription took {processing_time:.2f}s: '{text}'")
        
#         # Only process if we have meaningful text
#         if text and len(text) > 2:
#             self.last_transcription_time[session_id] = time.time()
#             if self.on_transcript:
#                 await self.on_transcript(session_id, text)

#     def register_callback(self, coro):
#         self.on_transcript = coro

#     async def transcribe_file(self, filepath: str):
#         """Optimized file transcription for recorded audio"""
#         start_time = time.time()
        
#         try:
#             data, samplerate = sf.read(filepath, dtype='int16')
#         except Exception as e:
#             print(f"[Whisper] Failed to read audio file {filepath}: {e}")
#             return {"text": "", "language": "en"}
            
#         if samplerate != settings.sample_rate:
#             print(f"[Whisper] File sample rate: {samplerate}, expected: {settings.sample_rate}")
            
#         audio_array = data.astype(np.float32) / 32768.0
        
#         # Check if audio has sufficient content
#         max_amplitude = np.abs(audio_array).max()
#         duration = len(audio_array) / samplerate
        
#         print(f"[Whisper] Audio duration: {duration:.2f}s, max amplitude: {max_amplitude}")
        
#         # More lenient thresholds for file transcription
#         if max_amplitude < 0.005 or duration < 0.3:
#             print(f"[Whisper] Audio too quiet or short, skipping transcription")
#             return {"text": "", "language": "en"}

#         loop = asyncio.get_running_loop()
        
#         # Optimized parameters for file transcription
#         segments, info = await loop.run_in_executor(None, lambda: self.model.transcribe(
#             audio_array,
#             beam_size=2,  # Slightly higher for files but still fast
#             language="en",
#             vad_filter=True,
#             vad_parameters=dict(
#                 min_silence_duration_ms=400,
#                 threshold=0.3,
#             ),
#             initial_prompt="This is a phone conversation about business solutions and lead qualification.",
#             condition_on_previous_text=False,  # Faster processing
#         ))

#         text = " ".join(segment.text for segment in segments).strip()
#         language = info.language if hasattr(info, "language") else "en"
        
#         processing_time = time.time() - start_time
#         print(f"[Whisper] File transcription took {processing_time:.2f}s")
#         print(f"[Whisper] Segments: {[(s.start, s.end, s.text) for s in segments]}")
#         print(f"[Whisper] Final transcription: '{text}'")

#         return {"text": text, "language": language}

#     async def clear_buffer(self, session_id: str):
#         """Clear buffer for a session"""
#         async with self.lock:
#             if session_id in self.buffers:
#                 del self.buffers[session_id]
#             if session_id in self.last_transcription_time:
#                 del self.last_transcription_time[session_id]

# whisper_service = WhisperBufferService()