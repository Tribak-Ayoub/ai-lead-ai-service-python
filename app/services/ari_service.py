import ari

client = ari.connect('http://localhost:8088', 'aiuser', 'SuperSecretPass')

def on_start(channel_obj, ev):
    print(f"[+] Incoming call from {channel_obj.json.get('caller', {}).get('number', 'Unknown')}")
    channel_obj.answer()
    channel_obj.play(media='sound:hello-world')
    # TODO: Start streaming audio or recording

client.on_channel_event('StasisStart', on_start)

def run_ari():
    print("[*] Starting ARI event loop...")
    client.run(apps='ai-assistant')

if __name__ == '__main__':
    run_ari()
