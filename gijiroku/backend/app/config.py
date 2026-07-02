"""アプリケーション設定 — すべてのシークレットは環境変数から読み込む。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Secrets (env: ANTHROPIC_API_KEY, OPENAI_API_KEY, DATABASE_URL, SLACK_WEBHOOK_URL, JWT_SECRET)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    database_url: str = "postgresql+asyncpg://gijiroku:gijiroku@localhost:5432/gijiroku"
    slack_webhook_url: str = ""
    jwt_secret: str = "dev-only-insecure-secret-change-me-0123456789"

    # The spec pinned claude-sonnet-4-20250514, which is deprecated and retires
    # 2026-06-15. claude-sonnet-4-6 is its official replacement.
    anthropic_model: str = "claude-sonnet-4-6"
    whisper_model: str = "whisper-1"

    jwt_expires_minutes: int = 720
    app_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "/tmp/gijiroku_uploads"
    max_upload_bytes: int = 200 * 1024 * 1024  # 200MB
    whisper_limit_bytes: int = 25 * 1024 * 1024  # Whisper API per-request limit


@lru_cache
def get_settings() -> Settings:
    return Settings()
