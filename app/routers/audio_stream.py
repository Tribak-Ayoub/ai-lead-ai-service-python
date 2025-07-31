# # app/routers/audio_stream.py
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from starlette.websockets import WebSocketState
# from app.services.whisper_buffer_service import AudioBuffer

# router = APIRouter()

# # Define your callback function
# def on_transcription(text: str):
#     print(">> Final Transcribed:", text)

# # Initialize buffer
# audio_buffer = AudioBuffer()
# audio_buffer.start(callback=on_transcription)

# @router.websocket("/ws/audio")
# async def audio_stream_ws(websocket: WebSocket):
#     await websocket.accept()
#     print("[*] WebSocket accepted")

#     try:
#         while websocket.application_state == WebSocketState.CONNECTED:
#             chunk = await websocket.receive_bytes()
#             audio_buffer.add_chunk(chunk)

#     except WebSocketDisconnect:
#         print("[*] WebSocket disconnected")
# # app/routers/audio_stream.py
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from starlette.websockets import WebSocketState
# from app.services.whisper_buffer_service import AudioBuffer

# router = APIRouter()

# # Define your callback function
# def on_transcription(text: str):
#     print(">> Final Transcribed:", text)

# # Initialize buffer
# audio_buffer = AudioBuffer()
# audio_buffer.start(callback=on_transcription)

# @router.websocket("/ws/audio")
# async def audio_stream_ws(websocket: WebSocket):
#     await websocket.accept()
#     print("[*] WebSocket accepted")

#     try:
#         while websocket.application_state == WebSocketState.CONNECTED:
#             chunk = await websocket.receive_bytes()
#             audio_buffer.add_chunk(chunk)

#     except WebSocketDisconnect:
#         print("[*] WebSocket disconnected")
