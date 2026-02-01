"""API routes for the YouTube downloader."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import ValidationError
from redis import Redis
from rq import Queue

from ytdl.config import settings
from ytdl.errors import ERROR_MESSAGES, ErrorCode
from ytdl.models import (
    CreateJobRequest,
    CreateJobResponse,
    ErrorResponse,
    JobProgress,
    JobStatus,
    JobStatusResponse,
    ProgressStage,
)

router = APIRouter()


def get_redis() -> Redis:
    """Get Redis connection."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def verify_token(x_api_token: Annotated[str | None, Header()] = None) -> str:
    """Verify API token from header."""
    if not x_api_token or x_api_token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                error_code=ErrorCode.UNAUTHORIZED,
                message=ERROR_MESSAGES[ErrorCode.UNAUTHORIZED],
            ).model_dump(),
        )
    return x_api_token


def get_job_data(redis: Redis, job_id: str) -> dict | None:
    """Get job data from Redis."""
    data = redis.get(f"job:{job_id}")
    if data:
        return json.loads(data)
    return None


def set_job_data(redis: Redis, job_id: str, data: dict) -> None:
    """Set job data in Redis with 24h TTL."""
    redis.setex(f"job:{job_id}", 86400, json.dumps(data, default=str))


@router.post(
    "/jobs",
    response_model=CreateJobResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def create_job(
    request: CreateJobRequest,
    _token: Annotated[str, Depends(verify_token)],
    wait: bool = False,
    timeout: int = 300,
) -> CreateJobResponse | JobStatusResponse:
    """
    Create a new video download job.

    Args:
        request: Job creation request with URL and quality
        wait: If True, wait until job completes and return full status with download_url
        timeout: Max seconds to wait (default 300 = 5 minutes, max 600)
    """
    redis = get_redis()

    # Rate limiting check
    rate_key = f"rate:{_token}"
    current = redis.get(rate_key)
    if current and int(current) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorResponse(
                error_code=ErrorCode.RATE_LIMITED,
                message=ERROR_MESSAGES[ErrorCode.RATE_LIMITED],
            ).model_dump(),
        )

    # Increment rate limit counter
    pipe = redis.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, 60)
    pipe.execute()

    # Create job
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "url": request.url,
        "quality": request.quality.value,
        "status": JobStatus.QUEUED.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    set_job_data(redis, job_id, job_data)

    # Enqueue job for processing
    queue = Queue(connection=Redis.from_url(settings.redis_url))
    queue.enqueue(
        "ytdl.worker.process_job",
        job_id,
        job_timeout=600,  # 10 minutes timeout
    )

    # If not waiting, return immediately
    if not wait:
        return CreateJobResponse(job_id=job_id)

    # Long-polling: wait until job is done/error or timeout
    timeout = min(timeout, 600)
    elapsed = 0
    poll_interval = 2

    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        job_data = get_job_data(redis, job_id)
        if job_data and job_data["status"] in [JobStatus.DONE.value, JobStatus.ERROR.value]:
            break

    # Get final job data and return full status
    job_data = get_job_data(redis, job_id)
    response = JobStatusResponse(
        job_id=job_data["job_id"],
        status=JobStatus(job_data["status"]),
    )

    if job_data["status"] == JobStatus.DONE.value:
        response.download_url = job_data.get("download_url")
        if "expires_at" in job_data:
            response.expires_at = datetime.fromisoformat(job_data["expires_at"])
        response.filename = job_data.get("filename")

    if job_data["status"] == JobStatus.ERROR.value:
        response.error_code = ErrorCode(job_data.get("error_code", ErrorCode.INTERNAL_ERROR))
        response.message = job_data.get("message", ERROR_MESSAGES[response.error_code])

    return response


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_job_status(
    job_id: str,
    _token: Annotated[str, Depends(verify_token)],
    wait: bool = False,
    timeout: int = 300,
) -> JobStatusResponse:
    """
    Get the status of a download job.

    Args:
        job_id: The job ID to check
        wait: If True, wait until job is done or error (long-polling)
        timeout: Max seconds to wait (default 300 = 5 minutes, max 600)
    """
    redis = get_redis()

    # Cap timeout at 10 minutes
    timeout = min(timeout, 600)

    # Long-polling: wait until job is done/error or timeout
    if wait:
        elapsed = 0
        poll_interval = 2  # Check every 2 seconds

        while elapsed < timeout:
            job_data = get_job_data(redis, job_id)

            if not job_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorResponse(
                        error_code=ErrorCode.JOB_NOT_FOUND,
                        message=ERROR_MESSAGES[ErrorCode.JOB_NOT_FOUND],
                    ).model_dump(),
                )

            # If job is done or error, return immediately
            if job_data["status"] in [JobStatus.DONE.value, JobStatus.ERROR.value]:
                break

            # Wait and try again
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    job_data = get_job_data(redis, job_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code=ErrorCode.JOB_NOT_FOUND,
                message=ERROR_MESSAGES[ErrorCode.JOB_NOT_FOUND],
            ).model_dump(),
        )

    response = JobStatusResponse(
        job_id=job_data["job_id"],
        status=JobStatus(job_data["status"]),
    )

    # Add progress info if running
    if job_data["status"] == JobStatus.RUNNING.value and "progress" in job_data:
        response.progress = JobProgress(
            stage=ProgressStage(job_data["progress"]["stage"]),
            pct=job_data["progress"]["pct"],
        )

    # Add download URL if done
    if job_data["status"] == JobStatus.DONE.value:
        response.download_url = job_data.get("download_url")
        if "expires_at" in job_data:
            response.expires_at = datetime.fromisoformat(job_data["expires_at"])
        response.filename = job_data.get("filename")

    # Add error info if failed
    if job_data["status"] == JobStatus.ERROR.value:
        response.error_code = ErrorCode(job_data.get("error_code", ErrorCode.INTERNAL_ERROR))
        response.message = job_data.get("message", ERROR_MESSAGES[response.error_code])

    return response
