import subprocess
import tempfile
import os
import soundfile as sf
import resampy
from pathlib import Path
from app.core.config import settings

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
        "model": Path("piper_tts/models/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx"),
        "config": Path("piper_tts/models/fr/fr_FR/gilles/low/fr_FR-gilles-low.onnx.json"),
    },
}

PIPER_BIN = Path(settings.piper_binary)

def synthesize_with_piper(text: str, lang: str = None, sample_rate: int = 8000) -> str:
    """
    Synthesize text to speech with Piper TTS.
    
    Args:
        text: Text to synthesize
        lang: Language code (en, ar, fr)
        sample_rate: Target sample rate (default 8000 for Asterisk compatibility)
    
    Returns:
        Path to the generated WAV file
    """
    if lang is None or lang not in VOICE_MODELS:
        lang = "en"

    model_path = VOICE_MODELS[lang]["model"]
    config_path = VOICE_MODELS[lang]["config"]

    if not PIPER_BIN.exists():
        raise FileNotFoundError(f"Piper binary not found: {PIPER_BIN}")
    if not model_path.exists():
        raise FileNotFoundError(f"Piper model not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Piper config not found: {config_path}")

    # Create temporary file for Piper output (at original sample rate)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_piper:
        piper_output_path = tmp_piper.name

    # Create final output file (at target sample rate)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_final:
        final_output_path = tmp_final.name

    cmd = [
        str(PIPER_BIN),
        "--model", str(model_path),
        "--config", str(config_path),
        "--output_file", piper_output_path,
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
            timeout=30,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Piper failed: {proc.stderr}")

        if not os.path.exists(piper_output_path) or os.path.getsize(piper_output_path) < 1000:
            raise RuntimeError("Piper produced no or too small output file")

        # Read the Piper output and resample if needed
        data, sr = sf.read(piper_output_path)
        print(f"[Piper] Generated audio at {sr} Hz, target: {sample_rate} Hz")
        
        if sr != sample_rate:
            print(f"[Piper] Resampling from {sr} to {sample_rate} Hz")
            # Handle mono/stereo
            if len(data.shape) == 1:
                data_resampled = resampy.resample(data, sr, sample_rate)
            else:
                data_resampled = resampy.resample(data.T, sr, sample_rate).T
        else:
            data_resampled = data
        
        # Write final file at target sample rate
        sf.write(final_output_path, data_resampled, sample_rate, format='WAV', subtype='PCM_16')
        
        # Clean up temporary Piper output
        os.remove(piper_output_path)
        
        print(f"[Piper] Final audio saved at {sample_rate} Hz: {final_output_path}")
        return final_output_path

    except Exception as e:
        # Clean up on error
        if os.path.exists(piper_output_path):
            os.remove(piper_output_path)
        if os.path.exists(final_output_path):
            os.remove(final_output_path)
        raise e

def synthesize_bytes(text: str, lang: str = None, sample_rate: int = 8000) -> bytes:
    """
    Synthesize text to speech and return as bytes.
    
    Args:
        text: Text to synthesize
        lang: Language code
        sample_rate: Target sample rate (default 8000 for Asterisk)
    
    Returns:
        WAV file bytes
    """
    wav_path = synthesize_with_piper(text, lang=lang, sample_rate=sample_rate)
    try:
        with open(wav_path, "rb") as f:
            return f.read()
    finally:
        os.remove(wav_path)