from fastapi import FastAPI
from pydantic import BaseModel
from gtts import gTTS
import os

app = FastAPI()

class AudioInput(BaseModel):
    text: str

@app.post("/process_audio/")
async def process_audio(audio: AudioInput):
    # Step 1: Simulate AI reply
    if "price" in audio.text.lower():
        reply = "Our product costs 99 dirhams."
    elif "hello" in audio.text.lower():
        reply = "Hello! How can I help you today?"
    else:
        reply = "I'm sorry, could you please repeat that?"

    # Step 2: Use gTTS to generate reply audio
    tts = gTTS(text=reply, lang='en')
    output_path = "/var/lib/asterisk/sounds/ai/tts-response.wav"
    mp3_path = "/tmp/tts-response.mp3"

    tts.save(mp3_path)

    # Convert MP3 to WAV (Asterisk prefers WAV)
    os.system(f"ffmpeg -y -i {mp3_path} -ar 8000 -ac 1 -f wav {output_path}")

    return {
        "intent": "simulated",
        "response_text": reply
    }
