from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Ollama ───────────────────────────────────────────────────────────────
    # gpt-oss:20b is a solid 20B open-weights model via Ollama.
    # Other good alternatives you can swap in:
    #   • mistral:7b-instruct    – fast, lower RAM (~6 GB)
    #   • llama3:8b-instruct     – very capable at instruction-following
    #   • llama3:70b-instruct    – highest quality, needs ~40 GB VRAM
    #   • mixtral:8x7b-instruct  – MoE, fast for its quality
    #   • deepseek-coder:33b     – if you want code-aware rule generation
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: int = 300          # seconds; 20B models can take 3-5 min on CPU
    OLLAMA_MAX_TOKENS: int = 2048

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Fraud Rule Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    MAX_UPLOAD_MB: int = 100
    SESSION_DIR: str = "/tmp/fraud_sessions"  # where uploaded CSVs are cached

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()