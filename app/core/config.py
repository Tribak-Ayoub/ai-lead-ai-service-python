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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
