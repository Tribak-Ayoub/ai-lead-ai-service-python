import asyncio
from app.services.whisper_service import transcribe_audio_file

async def main():
    file_path = "audio_samples/test_ar.wav"
    result = await transcribe_audio_file(file_path)
    print("Transcription:", result["transcription"])
    print("Language:", result["language"])

if __name__ == "__main__":
    asyncio.run(main())
