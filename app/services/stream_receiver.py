import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)

clients = set()

async def handler(websocket, path):
    clients.add(websocket)
    logging.info("Client connected")
    try:
        async for message in websocket:
            logging.info(f"Received audio chunk: {len(message)} bytes")
            # Here: push to STT microservice
    except websockets.ConnectionClosed:
        logging.warning("WebSocket closed")
    finally:
        clients.remove(websocket)

async def start_ws_server():
    logging.info("Starting WebSocket server...")
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    await server.wait_closed()
