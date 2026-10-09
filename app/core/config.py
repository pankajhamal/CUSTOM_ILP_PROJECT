"""Application settings loaded from environment / `.env` via pydantic-settings.

Settings are validated once at import time and exposed as a cached singleton
through :func:`get_settings`. Import the module-level ``settings`` for convenience.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Custom ILP ASE"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://ilp:ilp@localhost:5432/ilp_ase"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Security ---
    secret_key: str = "change-me-to-a-long-random-string"

    # --- Rafiki webhook (inbound) security ---
    # Env name matches Rafiki's RAFIKI_SIGNATURE_SECRET (old RAFIKI_WEBHOOK_SECRET
    # still accepted) so the shared secret has one name on both sides.
    rafiki_webhook_secret: str = Field(
        default="change-me-shared-with-rafiki",
        validation_alias=AliasChoices("RAFIKI_SIGNATURE_SECRET", "RAFIKI_WEBHOOK_SECRET"),
    )
    # Rafiki sends the webhook signature in the "rafiki-signature" header.
    rafiki_webhook_signature_header: str = "rafiki-signature"
    rafiki_webhook_signature_version: str = "1"
    rafiki_webhook_tolerance_seconds: int = 300

    # --- Rafiki Admin API (outbound GraphQL) ---
    # Env names match Rafiki's ADMIN_API_SECRET / ADMIN_SIGNATURE_VERSION /
    # OPERATOR_TENANT_ID (old RAFIKI_GRAPHQL_* / RAFIKI_TENANT_ID still accepted).
    rafiki_graphql_url: str = "http://localhost:3011/graphql"
    rafiki_graphql_signature_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_API_SECRET", "RAFIKI_SIGNATURE_SECRET"),
    )
    rafiki_graphql_signature_version: str = Field(
        default="1",
        validation_alias=AliasChoices("ADMIN_SIGNATURE_VERSION", "RAFIKI_GRAPHQL_SIGNATURE_VERSION"),
    )
    rafiki_tenant_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPERATOR_TENANT_ID", "RAFIKI_TENANT_ID"),
    )
    rafiki_http_timeout_seconds: float = 30.0

    # --- Default provisioning asset ---
    default_asset_id: str | None = None
    default_asset_code: str = "USD"
    default_asset_scale: int = 2

    # --- Wallet address base ---
    wallet_address_base_url: str = "https://wallet.example"

    # --- OpenTelemetry ---
    otel_enabled: bool = False
    otel_service_name: str = "custom-ilp-ase"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    @field_validator(
        "default_asset_id",
        "rafiki_tenant_id",
        "rafiki_graphql_signature_secret",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        """Treat empty/whitespace env values (e.g. ``DEFAULT_ASSET_ID=``) as unset."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """Ensure the DB URL uses an async driver SQLAlchemy understands."""
        allowed_prefixes = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not v.startswith(allowed_prefixes):
            raise ValueError(
                "DATABASE_URL must use an async driver, e.g. "
                "'postgresql+asyncpg://…' or 'sqlite+aiosqlite://…'"
            )
        # Validate the Postgres shape when applicable (sqlite skips this).
        if v.startswith("postgresql+asyncpg://"):
            PostgresDsn(v.replace("+asyncpg", ""))
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()


settings = get_settings()
