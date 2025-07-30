# routers/stt.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.whisper_service import transcribe_audio_stream
from app.services.intent_service import detect_intent  # 👈 new

router = APIRouter()

@router.websocket("/api/whisper/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("connection open")

    audio_chunks = []

    try:
        while True:
            data = await websocket.receive_bytes()
            if data == b"__end__":
                break
            audio_chunks.append(data)

    except WebSocketDisconnect:
        print("WebSocket disconnected")

    finally:
        print("Transcribing", len(b"".join(audio_chunks)), "bytes of audio...")
        text = transcribe_audio_stream(audio_chunks)

        if text:
            print("Transcription result:", text)
            try:
                intent_result = detect_intent(text)  # 👈 call intent service
            except Exception as e:
                intent_result = {"error": str(e)}

            await websocket.send_json({
                "text": text,
                "intent": intent_result
            })
        else:
            print("Final transcription failed")
            await websocket.send_json({"error": "Transcription failed"})

        await websocket.close()
        print("connection closed")
