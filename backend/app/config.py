"""
Application settings loaded from environment variables using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the application.
    Values are loaded from the .env file and can be overridden by environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Encryption (AES-256-GCM)
    encryption_key: str

    # Email (Resend)
    resend_api_key: str = "re_dummy_key_for_dev"
    from_email: str = "onboarding@resend.dev"

    # App
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"
    api_prefix: str = "/api/v1"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


settings = Settings()
