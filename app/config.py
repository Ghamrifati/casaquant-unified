"""CasaQuant Unified — Application configuration."""

from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────
    casaquant_env: Literal["development", "production"] = Field(
        default="development",
        alias="CASAQUANT_ENV",
    )

    # ── Database ───────────────────────────────────────────────────
    database_url: PostgresDsn | str = Field(
        default="sqlite:///data/casaquant_unified.db",
        alias="DATABASE_URL",
    )

    # ── Cache / Queue ───────────────────────────────────────────────
    redis_url: RedisDsn | str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    # ── Security ───────────────────────────────────────────────────
    api_key: SecretStr = Field(
        default=SecretStr("dev_key_change_me"),
        alias="API_KEY",
    )

    # ── Ollama / AI ──────────────────────────────────────────────
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field(default="gemma4:latest", alias="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=120, alias="OLLAMA_TIMEOUT")
    ollama_max_retries: int = Field(default=3, alias="OLLAMA_MAX_RETRIES")
    ollama_backoff: int = Field(default=2, alias="OLLAMA_BACKOFF")

    # ── Scraping ───────────────────────────────────────────────────
    casabourse_api_url: str = Field(
        default="https://api.casabourse.ma",
        alias="CASABOURSE_API_URL",
    )
    wafabourse_url: str = Field(
        default="https://www.wafabourse.com",
        alias="WAFABOURSE_URL",
    )
    scraper_timeout: int = Field(default=40, alias="SCRAPER_TIMEOUT")
    scraper_max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")

    # ── Notifications ──────────────────────────────────────────────
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # ── BVC Fees ───────────────────────────────────────────────────
    bvc_tax_rate: float = Field(default=0.001, alias="BVC_TAX_RATE")
    bvc_brokerage_rate: float = Field(default=0.006, alias="BVC_BROKERAGE_RATE")
    bvc_vat_rate: float = Field(default=0.10, alias="BVC_VAT_RATE")
    bvc_min_brokerage: float = Field(default=10.0, alias="BVC_MIN_BROKERAGE")

    # ── Derived properties ─────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.casaquant_env == "production"

    @property
    def is_sqlite(self) -> bool:
        return isinstance(self.database_url, str) and self.database_url.startswith("sqlite")

    def get_api_key_plain(self) -> str:
        return self.api_key.get_secret_value()


settings = Settings()
