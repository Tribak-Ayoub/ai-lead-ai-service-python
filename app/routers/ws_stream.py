import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header
from app.services.whisper_buffer_service import whisper_service
from app.services.intent_service import qualify_transcript
from app.routers.tts import synthesize_text

router = APIRouter()

@router.websocket("/ws/audio")
async def websocket_audio(ws: WebSocket, x_session_id: str | None = Header(None)):
    await ws.accept()
    session_id = x_session_id or str(uuid.uuid4())
    print(f"[ws] Connected session {session_id}")

    async def on_transcript(sid, text):
        if sid != session_id:
            return  # Ignore others

        print(f"[stt] Transcript for {sid}: {text}")

        qual = await qualify_transcript(sid, text)
        tts_audio_bytes = await synthesize_text(qual["reply_text"], sid)

        await ws.send_json({
            "transcript": text,
            "intent": qual["intent"],
            "lead_score": qual["lead_score"],
            "reply_text": qual["reply_text"]
        })

        with open(f"/tmp/tts_{sid}.wav", "wb") as f:
            f.write(tts_audio_bytes)

    whisper_service.register_callback(on_transcript)

    try:
        while True:
            chunk = await ws.receive_bytes()
            await whisper_service.add_chunk(session_id, chunk)

    except WebSocketDisconnect:
        print(f"[ws] Disconnected session {session_id}")
        whisper_service.register_callback(None)  # Cleanup callback
