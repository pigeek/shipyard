from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = True
    secret_key: str = "change-me"
    app_name: str = "Shipyard"
    base_url: str = "http://localhost:8000"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://shipyard:shipyard@localhost:5432/shipyard"

    # --- Redis (cache + arq broker) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth ---
    access_token_lifetime_seconds: int = 3600
    cookie_secure: bool = False

    # --- Email ---
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    email_from: str = "no-reply@shipyard.local"

    # --- Stripe ---
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:8000/billing/success"
    stripe_cancel_url: str = "http://localhost:8000/billing/cancel"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
