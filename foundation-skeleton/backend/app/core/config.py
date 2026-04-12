from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    app_env: str = "development"
    app_secret_key: str = Field(default="change-me", alias="APP_SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    database_url: str = Field(alias="DATABASE_URL")
    enable_telemetry: bool = Field(default=False, alias="ENABLE_TELEMETRY")
    redis_url: str = Field(alias="REDIS_URL")
    otel_service_name: str = Field(default="foundation-backend", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_console_exporter_enabled: bool = Field(default=False, alias="OTEL_CONSOLE_EXPORTER_ENABLED")
    app_cors_origins: str = Field(default="http://localhost:3000", alias="APP_CORS_ORIGINS")
    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        unsafe_values = {
            "",
            "change-me",
            "secret",
            "test",
            "demo",
            "password",
            "123456",
        }

        secret = self.app_secret_key.strip()

        if self.app_env.lower() == "production":
            if not secret or secret in unsafe_values or secret.startswith("env:"):
                raise ValueError("APP_SECRET_KEY is unsafe for production")

        return self
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
