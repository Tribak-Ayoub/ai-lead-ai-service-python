from faster_whisper import WhisperModel

# Use "base", "small", or "medium" depending on RAM
model = WhisperModel("base")

def transcribe_audio(file_path):
    segments, _ = model.transcribe(file_path)
    return " ".join([segment.text for segment in segments])
