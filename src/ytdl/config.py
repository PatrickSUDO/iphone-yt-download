"""Application configuration using pydantic-settings."""

from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageMode(StrEnum):
    """Storage backend mode."""

    LOCAL = "local"
    R2 = "r2"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Authentication
    api_token: str = "test-token"  # Default for local testing

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage mode
    storage_mode: StorageMode = StorageMode.LOCAL

    # Local storage settings
    local_storage_dir: str = "./downloads"
    base_url: str = "http://localhost:8000"  # For generating download URLs

    # Cloudflare R2 (optional, only required if storage_mode=r2)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str | None = None

    # Download settings
    download_dir: str = "/tmp/ytdl-downloads"
    max_concurrent_jobs: int = 2
    concurrent_fragments: int = 8

    # URL settings
    url_expiry_minutes: int = 30

    # Rate limiting
    rate_limit_per_minute: int = 10

    @property
    def r2_endpoint_url(self) -> str:
        """Get R2 S3-compatible endpoint URL."""
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def is_r2_configured(self) -> bool:
        """Check if R2 is properly configured."""
        return all([
            self.r2_account_id,
            self.r2_access_key_id,
            self.r2_secret_access_key,
            self.r2_bucket_name,
        ])


settings = Settings()
