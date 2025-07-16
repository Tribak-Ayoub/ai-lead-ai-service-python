import subprocess
import os

PIPER_PATH = os.path.abspath("piper_tts/piper/piper")

VOICE_MODELS = {
    "ar": "piper_tts/models/ar/ar_JO/kareem/low/ar_JO-kareem-low.onnx",
    "en": "piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx",
    "fr": "piper_tts/models/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx"
}

def synthesize_text(text, lang="en", output_path="output.wav"):
    model_path = VOICE_MODELS.get(lang)
    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"Voice model for '{lang}' not found.")

    config_path = model_path + ".json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Model config file missing: {config_path}")

    cmd = [
        PIPER_PATH,
        "-m", model_path,
        "-c", config_path,
        "-f", output_path
    ]

    print("[DEBUG] Running Piper with stdin text input...")

    # Send the text input via stdin
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(input=text)

    print("[DEBUG] Piper stdout:", stdout)
    print("[DEBUG] Piper stderr:", stderr)

    if process.returncode != 0:
        raise RuntimeError(f"Piper failed: {stderr}")

    return output_path
