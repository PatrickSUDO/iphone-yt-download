"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Authentication
    api_token: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Cloudflare R2
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_public_url: str | None = None  # Optional custom domain

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


settings = Settings()
