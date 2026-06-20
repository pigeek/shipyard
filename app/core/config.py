from functools import lru_cache
from typing import Literal

from pydantic import model_validator
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

    # --- Realtime (WebSocket / ASGI push; see app/core/realtime.py) ---
    # "memory" (default) is in-process — fine for tests + single-process dev.
    # "redis" fans messages out across workers via pub/sub (compose sets it).
    realtime_provider: Literal["memory", "redis"] = "memory"

    # --- Auth ---
    access_token_lifetime_seconds: int = 3600
    refresh_token_lifetime_seconds: int = 60 * 60 * 24 * 30  # 30 days
    cookie_secure: bool = False
    # Which auth transports this deployment accepts (ADR 0001 §6). Disabling the
    # cookie transport yields a bearer-only API with no CSRF surface; disabling
    # bearer yields a cookie-only (SSR/SPA) deployment. At least one must be on.
    auth_cookie_enabled: bool = True
    auth_bearer_enabled: bool = True

    # --- CORS (separate-origin / dev SPA) ---
    cors_origins: list[str] = []

    # --- OAuth (social login; mounted only when a provider is configured) ---
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    # --- Email ---
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    email_from: str = "no-reply@shipyard.local"

    # --- Object storage (S3 / MinIO; see app/core/storage.py) ---
    # "memory" (default) keeps dev/tests infra-free; compose sets "s3".
    storage_provider: Literal["memory", "s3"] = "memory"
    s3_endpoint_url: str | None = None  # e.g. http://minio:9000; None = real AWS
    # Endpoint baked into presigned URLs handed to the browser. Needed when the
    # API reaches MinIO as http://minio:9000 but the browser only knows localhost.
    s3_public_endpoint_url: str | None = None
    s3_bucket: str = "shipyard"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    presigned_url_ttl: int = 3600  # presigned GET (download) expiry
    upload_credential_ttl: int = 600  # presigned POST (upload) expiry (10 min)
    max_upload_size: int = 10 * 1024 * 1024  # 10 MB ceiling enforced by the bucket
    orphan_upload_max_age: int = 24 * 3600  # delete never-confirmed uploads after 24h

    # --- Stripe ---
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:8000/billing/success"
    stripe_cancel_url: str = "http://localhost:8000/billing/cancel"

    @model_validator(mode="after")
    def _at_least_one_transport(self) -> "Settings":
        if not (self.auth_cookie_enabled or self.auth_bearer_enabled):
            raise ValueError("At least one auth transport must be enabled.")
        return self

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
