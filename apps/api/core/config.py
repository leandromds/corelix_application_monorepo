"""
Core configuration module using Pydantic Settings.
Loads environment variables and provides type-safe access to configuration.
"""

import json
from typing import Any, get_origin

from pydantic import Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _FlexibleEnvSource(EnvSettingsSource):
    """
    Custom EnvSettingsSource that supports both comma-separated strings and JSON
    arrays for List[str] fields.

    Problem: pydantic-settings 2.x marks List[str] as "complex" and tries to
    JSON-parse the raw env var string inside prepare_field_value() — before any
    field_validator runs. A value like 'http://a.com,http://b.com' is not valid
    JSON, so it raises SettingsError and the validator never executes.

    Fix: for list fields, catch the JSON parse failure and fall back to
    comma-splitting. All other complex types keep the original behavior.

    Accepted formats for List[str] fields:
        CORS_ORIGINS=http://localhost:5173                          # single value
        CORS_ORIGINS=http://localhost:5173,http://localhost:3000    # comma-separated
        CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]  # JSON array
    """

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        # Note: do NOT gate on value_is_complex — pydantic-settings 2.14 reports
        # False for list[str] fields, but the parent's prepare_field_value still
        # calls decode_complex_value (which JSON-parses) for list annotations.
        # We intercept here based solely on the field annotation.
        if isinstance(value, str) and get_origin(field.annotation) is list:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                # Fallback: comma-separated string → list
                return [v.strip() for v in value.split(",") if v.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _FlexibleDotEnvSource(_FlexibleEnvSource, DotEnvSettingsSource):
    """
    Same fix applied to the .env file source.

    MRO: _FlexibleDotEnvSource → _FlexibleEnvSource → DotEnvSettingsSource
         → EnvSettingsSource → PydanticBaseSettingsSource

    __init__ resolves to DotEnvSettingsSource (handles file loading).
    prepare_field_value resolves to _FlexibleEnvSource (handles comma-split).
    """


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All sensitive values should be loaded from .env file (never committed).
    See .env.example for required variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string with asyncpg driver",
    )

    # JWT Authentication
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Secret key for JWT signing (use openssl rand -hex 32)",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        ge=1,
        description="Access token expiration time in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        ge=1,
        description="Refresh token expiration time in days",
    )

    # Anthropic API (Claude)
    ANTHROPIC_API_KEY: str = Field(
        ...,
        description="Anthropic API key for Claude integration",
    )

    # WhatsApp Business API (Meta Cloud API)
    WHATSAPP_VERIFY_TOKEN: str = Field(
        ...,
        description="Webhook verification token for WhatsApp",
    )
    WHATSAPP_APP_SECRET: str = Field(
        ...,
        description="App secret for WhatsApp webhook validation",
    )

    # Application
    ENVIRONMENT: str = Field(
        default="development",
        description="Environment name (development, staging, production)",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API host binding address",
    )
    API_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API port",
    )

    # CORS
    # Accepted formats (all handled by _FlexibleEnvSource):
    #   single:          CORS_ORIGINS=http://localhost:5173
    #   comma-separated: CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    #   JSON array:      CORS_ORIGINS=["http://localhost:5173"]
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Encryption (for sensitive data at rest)
    ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet encryption key for sensitive data (use cryptography.fernet.Fernet.generate_key())",
    )

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is one of the allowed values."""
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got '{v}'")
        return v.lower()

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic migrations)."""
        return self.DATABASE_URL.replace("+asyncpg", "")

    @classmethod
    def settings_customise_sources(  # type: ignore[override]
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        **kwargs: Any,  # absorbs secrets_settings (2.1–2.3) or file_secret_settings (2.4+)
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Replace the default env and dotenv sources with flexible versions that
        accept comma-separated strings for List[str] fields in addition to the
        JSON array format required by pydantic-settings 2.x out of the box.

        Priority (highest → lowest): init → env vars → .env file → secrets

        Note: pydantic-settings renamed secrets_settings → file_secret_settings in 2.4.
        Using **kwargs keeps this override compatible across the full 2.x range.
        """
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            _FlexibleEnvSource(settings_cls),
            _FlexibleDotEnvSource(settings_cls),
        ]
        # Re-include the secrets source regardless of its parameter name
        if kwargs:
            sources.append(next(iter(kwargs.values())))
        return tuple(sources)


# Global settings instance
settings = Settings()
