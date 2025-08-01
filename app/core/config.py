from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    google_api_key: str

    # ARI
    ari_username: str
    ari_password: str
    ari_base_url: str

    # Whisper
    whisper_model: str
    sample_rate: int
    chunk_duration_s: float

    # Piper
    default_tts_lang: str
    piper_binary: str

    # Gemini
    gemini_api_url: str  # full endpoint for Gemini-style intent call
    gemini_model: str    # optional: model identifier if you use it in prompt or URL

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
