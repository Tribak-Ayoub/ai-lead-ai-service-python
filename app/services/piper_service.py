import subprocess
import tempfile
import os
import soundfile as sf
import resampy
from pathlib import Path
from app.core.config import settings
import shutil

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


def convert_to_mulaw_with_ffmpeg(wav_path: str) -> str:
    """
    Use ffmpeg to convert WAV to 8000Hz mu-law (.ulaw) for Asterisk.
    """
    ulaw_path = wav_path.replace(".wav", ".ulaw")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", wav_path,
        "-ar", "8000",
        "-ac", "1",
        "-f", "mulaw",
        ulaw_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return ulaw_path


def synthesize_with_piper(text: str, lang: str = None, sample_rate: int = 8000, prefer_ulaw: bool = True) -> str:
    """
    Synthesize text to speech with Piper TTS, optionally convert to mu-law for Asterisk playback.

    Args:
        text: Text to synthesize
        lang: Language code (en, ar, fr)
        sample_rate: Target sample rate (default 8000 for Asterisk compatibility)
        prefer_ulaw: Try to output .ulaw if possible to reduce live transcoding.

    Returns:
        Path to generated audio file (either .ulaw or .wav).
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

    # Prepare temporary files
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_piper:
        piper_output_path = tmp_piper.name

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

        # Read and resample if needed
        data, sr = sf.read(piper_output_path)
        print(f"[Piper] Generated audio at {sr} Hz, target: {sample_rate} Hz")

        if sr != sample_rate:
            print(f"[Piper] Resampling from {sr} to {sample_rate} Hz")
            if len(data.shape) == 1:
                data_resampled = resampy.resample(data, sr, sample_rate)
            else:
                data_resampled = resampy.resample(data.T, sr, sample_rate).T
        else:
            data_resampled = data

        sf.write(final_output_path, data_resampled, sample_rate, format='WAV', subtype='PCM_16')
        print(f"[Piper] Final audio saved at {sample_rate} Hz: {final_output_path}")

        # Clean up intermediate file
        if os.path.exists(piper_output_path):
            os.remove(piper_output_path)

        # Try converting to mu-law if desired
        if prefer_ulaw:
            try:
                if shutil.which("ffmpeg"):
                    ulaw_path = convert_to_mulaw_with_ffmpeg(final_output_path)
                    print(f"[Piper] Converted to mu-law via ffmpeg: {ulaw_path}")
                    os.remove(final_output_path)
                    return ulaw_path
                else:
                    print("[Piper] ffmpeg not found; skipping mu-law conversion")
            except Exception as e:
                print(f"[Piper] mu-law conversion via ffmpeg failed, falling back to WAV: {e}")

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
    """
    audio_path = synthesize_with_piper(text, lang=lang, sample_rate=sample_rate)
    try:
        with open(audio_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
