"""RQ worker for processing download jobs."""

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redis import Redis

from ytdl.config import settings
from ytdl.downloader import download_video
from ytdl.errors import ErrorCode, YTDLError
from ytdl.models import JobStatus, ProgressStage
from ytdl.storage import generate_presigned_url, upload_file

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def get_redis() -> Redis:
    """Get Redis connection."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_job_data(redis: Redis, job_id: str) -> dict | None:
    """Get job data from Redis."""
    data = redis.get(f"job:{job_id}")
    if data:
        return json.loads(data)
    return None


def update_job(redis: Redis, job_id: str, **updates) -> None:
    """Update job data in Redis."""
    job_data = get_job_data(redis, job_id)
    if job_data:
        job_data.update(updates)
        redis.setex(f"job:{job_id}", 86400, json.dumps(job_data, default=str))


def process_job(job_id: str) -> None:
    """
    Process a download job.

    This function is called by RQ worker.
    """
    redis = get_redis()
    job_data = get_job_data(redis, job_id)

    if not job_data:
        logger.error(f"Job {job_id} not found")
        return

    url = job_data["url"]
    quality = job_data["quality"]

    # Create temporary directory for this job
    work_dir = Path(settings.download_dir) / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Update status to running
        update_job(
            redis,
            job_id,
            status=JobStatus.RUNNING.value,
            progress={"stage": ProgressStage.DOWNLOADING.value, "pct": 0},
        )

        # Progress callback
        def on_progress(stage: str, pct: int):
            update_job(
                redis,
                job_id,
                progress={"stage": stage, "pct": pct},
            )

        # Download video
        logger.info(f"Processing job {job_id}: {url} at {quality}p")
        output_file = download_video(url, quality, work_dir, on_progress)

        # Update progress - uploading
        update_job(
            redis,
            job_id,
            progress={"stage": ProgressStage.UPLOADING.value, "pct": 0},
        )

        # Upload to R2
        object_key = f"videos/{job_id}/{output_file.name}"
        upload_file(output_file, object_key)

        # Generate presigned URL
        download_url, expires_at = generate_presigned_url(object_key)

        # Update job as done
        update_job(
            redis,
            job_id,
            status=JobStatus.DONE.value,
            download_url=download_url,
            expires_at=expires_at.isoformat(),
            filename=output_file.name,
            object_key=object_key,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(f"Job {job_id} completed successfully")

    except YTDLError as e:
        logger.error(f"Job {job_id} failed: {e.code} - {e.message}")
        update_job(
            redis,
            job_id,
            status=JobStatus.ERROR.value,
            error_code=e.code.value,
            message=e.message,
        )

    except Exception as e:
        logger.error(f"Job {job_id} failed with unexpected error: {e}")
        update_job(
            redis,
            job_id,
            status=JobStatus.ERROR.value,
            error_code=ErrorCode.INTERNAL_ERROR.value,
            message=str(e),
        )

    finally:
        # Clean up work directory
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info(f"Cleaned up work directory: {work_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up work directory: {e}")
