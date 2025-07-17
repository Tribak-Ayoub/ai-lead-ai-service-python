import subprocess
import tempfile
import os
from pathlib import Path

# Adjust these paths to where your model and config actually are
PIPER_BIN = Path("piper_tts/piper/piper")  # Piper executable
PIPER_MODEL = Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx")
PIPER_CONFIG = Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx.json")

def synthesize_with_piper(text: str) -> str:
    if not PIPER_BIN.exists():
        raise FileNotFoundError(f"Piper binary not found at {PIPER_BIN}")
    if not PIPER_MODEL.exists():
        raise FileNotFoundError(f"Piper model not found at {PIPER_MODEL}")
    if not PIPER_CONFIG.exists():
        raise FileNotFoundError(f"Piper config not found at {PIPER_CONFIG}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        output_path = tmp_file.name

    result = subprocess.run(
        [
            str(PIPER_BIN),
            "--model", str(PIPER_MODEL),
            "--config", str(PIPER_CONFIG),
            "--output_file", output_path,
        ],
        input=text,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        # Remove the temp output if failed
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"Piper failed: {result.stderr}")

    return output_path
