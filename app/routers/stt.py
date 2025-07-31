# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from starlette.websockets import WebSocketState
# from app.services.whisper_buffer_service import AudioBuffer
# import asyncio

# router = APIRouter()

# # Global buffer (or you can make it per-connection if needed)
# audio_buffer = AudioBuffer(sample_rate=16000, interval=1)

# # Callback when transcription finishes
# def on_transcription(text: str):
#     print(">> Final Transcribed:", text)

# @router.websocket("/ws/audio")
# async def audio_stream_ws(websocket: WebSocket):
#     await websocket.accept()
#     print("[*] WebSocket accepted")

#     # Start the buffer with the callback if not running already
#     if not audio_buffer.running:
#         audio_buffer.start(callback=on_transcription)

#     try:
#         while websocket.application_state == WebSocketState.CONNECTED:
#             chunk = await websocket.receive_bytes()
#             audio_buffer.add_chunk(chunk)

#     except WebSocketDisconnect:
#         print("[*] WebSocket disconnected")
#         audio_buffer.stop()
