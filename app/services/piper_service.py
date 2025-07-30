import subprocess
import tempfile
import os
from pathlib import Path

# Define voice models for supported languages
VOICE_MODELS = {
    "en": {
        "model": Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx"),
        "config": Path("piper_tts/models/en/en_US/kathleen/low/en_US-kathleen-low.onnx.json"),
    },
    "ar": {
        "model": Path("piper_tts/models/ar/ar_JO/kareem/low/ar_JO-kareem-low.onnx"),
        "config": Path("piper_tts/models/ar/ar_JO/kareem/low/ar_JO-kareem-low.onnx.json"),
    },
    "fr": {
        # Fixed typo: removed extra 'p' in path
        "model": Path("piper_tts/models/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx"),
        "config": Path("piper_tts/models/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx.json"),
    },
}

PIPER_BIN = Path("piper_tts/piper/piper")

def synthesize_with_piper(text: str, lang: str = "en") -> str:
    """Synthesize speech using Piper for the given language, return WAV file path."""

    if lang not in VOICE_MODELS:
        print(f"[!] Language '{lang}' not supported, falling back to English")
        lang = "en"  # fallback

    model_path = VOICE_MODELS[lang]["model"]
    config_path = VOICE_MODELS[lang]["config"]

    if not PIPER_BIN.exists():
        raise FileNotFoundError(f"Piper binary not found: {PIPER_BIN}")
    if not model_path.exists():
        raise FileNotFoundError(f"Piper model not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Piper config not found: {config_path}")

    try:
        # Create temporary file for output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            output_path = tmp_file.name

        print(f"[*] Generating TTS for '{text[:30]}...' in language '{lang}'")
        
        # Run Piper TTS
        result = subprocess.run(
            [
                str(PIPER_BIN),
                "--model", str(model_path),
                "--config", str(config_path),
                "--output_file", output_path,
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=15,  # Increased timeout
        )

        if result.returncode != 0:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise RuntimeError(f"Piper error (code {result.returncode}): {result.stderr.strip()}")

        # Verify output file was created and has content
        if not os.path.exists(output_path):
            raise RuntimeError("Piper did not create output file")
        
        file_size = os.path.getsize(output_path)
        if file_size < 1000:  # Less than 1KB suggests empty or invalid file
            os.remove(output_path)
            raise RuntimeError(f"Piper output file too small ({file_size} bytes)")
        
        print(f"[*] TTS generated successfully: {file_size} bytes")
        return output_path

    except subprocess.TimeoutExpired:
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError("Piper timed out while generating speech (15s limit)")
    except Exception as e:
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"Piper execution failed: {str(e)}")