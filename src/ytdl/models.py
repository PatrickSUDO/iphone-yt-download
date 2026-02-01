"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ytdl.errors import ErrorCode


class Quality(StrEnum):
    """Video quality options."""

    Q480 = "480"
    Q720 = "720"
    Q1080 = "1080"
    BEST = "best"


class JobStatus(StrEnum):
    """Job processing status."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class ProgressStage(StrEnum):
    """Download progress stages."""

    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    UPLOADING = "uploading"


# Request models


class CreateJobRequest(BaseModel):
    """Request body for creating a new download job."""

    url: str = Field(..., description="YouTube video URL")
    quality: Quality = Field(default=Quality.Q720, description="Video quality")

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a YouTube URL."""
        v = v.strip()
        valid_hosts = (
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "www.youtu.be",
        )
        if not any(host in v for host in valid_hosts):
            raise ValueError("Only YouTube URLs are supported")
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# Response models


class JobProgress(BaseModel):
    """Job progress information."""

    stage: ProgressStage
    pct: int = Field(ge=0, le=100)


class CreateJobResponse(BaseModel):
    """Response for job creation."""

    job_id: str
    status: Literal[JobStatus.QUEUED] = JobStatus.QUEUED


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: JobStatus
    progress: JobProgress | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    filename: str | None = None
    error_code: ErrorCode | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response body."""

    error_code: ErrorCode
    message: str
