import subprocess
import tempfile
import os
from pathlib import Path

# === Configure TTS Voice ===
# You can switch between English or Arabic by adjusting these paths
# Example Arabic model (fallback) could be: "ar_MA-rahma-low.onnx"
PIPER_BIN = Path("piper_tts/piper/piper")
PIPER_MODEL = Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx")
PIPER_CONFIG = Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx.json")

def synthesize_with_piper(text: str) -> str:
    """Synthesize speech using Piper and return the path to the WAV file."""
    if not PIPER_BIN.exists():
        raise FileNotFoundError(f"Piper binary not found: {PIPER_BIN}")
    if not PIPER_MODEL.exists():
        raise FileNotFoundError(f"Piper model not found: {PIPER_MODEL}")
    if not PIPER_CONFIG.exists():
        raise FileNotFoundError(f"Piper config not found: {PIPER_CONFIG}")

    try:
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
            timeout=10,
        )

        if result.returncode != 0:
            os.remove(output_path)
            raise RuntimeError(f"Piper error: {result.stderr.decode().strip()}")

        return output_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("Piper timed out while generating speech.")
    except Exception as e:
        raise RuntimeError(f"Piper execution failed: {str(e)}")
