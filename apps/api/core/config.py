"""
Core configuration module using Pydantic Settings.
Loads environment variables and provides type-safe access to configuration.
"""

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins (comma-separated in .env)",
    )

    # Encryption (for sensitive data at rest)
    ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet encryption key for sensitive data (use cryptography.fernet.Fernet.generate_key())",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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


# Global settings instance
settings = Settings()
