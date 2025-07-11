import json
import requests
import websocket
import threading

ARI_USER = 'aiuser'
ARI_PASS = 'ai123'
ARI_URL = 'http://localhost:8088'
WS_URL = 'ws://localhost:8088/ari/events?api_key=aiuser:ai123&app=ai-assistant&subscribeAll=true'


def on_message(ws, message):
    data = json.loads(message)
    event_type = data.get("type")

    if event_type == "StasisStart":
        channel = data["channel"]
        channel_id = channel["id"]

        print(f"📞 Incoming call: {channel['caller']['number']}")

        # Answer the call
        requests.post(f"{ARI_URL}/ari/channels/{channel_id}/answer", auth=(ARI_USER, ARI_PASS))

        # Start recording
        requests.post(f"{ARI_URL}/ari/channels/{channel_id}/record",
                      auth=(ARI_USER, ARI_PASS),
                      data={
                          'name': 'call_recording',
                          'format': 'wav',
                          'beep': 'true',
                          'ifExists': 'overwrite'
                      })

        print("🎙️ Recording started...")

    elif event_type == "RecordingFinished":
        print("✅ Recording finished.")

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed")

def on_open(ws):
    print("🤖 ARI WebSocket connected and listening...")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(WS_URL,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open

    # Run the WebSocket in a separate thread
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    # Keep the script alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("🛑 Exiting...")
