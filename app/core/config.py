
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Custom ILP ASE"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://ilp:ilp@localhost:5432/ilp_ase"
    )

    # Security
    SECRET_KEY: str = "change-me"

    # Rafiki authentication
    RAFIKI_SIGNATURE_SECRET: str = ""
    RAFIKI_TENANT_ID: str = ""
    RAFIKI_API_SECRET: str = ""

    RAFIKI_ASSET_ID: str = ""
    RAFIKI_ASSET_CODE: str = ""
    RAFIKI_ASSET_SCALE: int
    # Rafiki GraphQL
    RAFIKI_GRAPHQL_URL: str = (
        "http://host.docker.internal:3011/graphql"
    )
    RAFIKI_GRAPHQL_SIGNATURE_VERSION: str = "1"

    # Wallet address
    WALLET_ADDRESS_BASE_URL: str = (
        "https://rafiki-backend.testnet.test/.well-known/pay"
    )

    # OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "custom-ilp-ase"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def IS_SQLITE(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
