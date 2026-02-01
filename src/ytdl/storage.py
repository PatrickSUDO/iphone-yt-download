"""Cloudflare R2 storage operations."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ytdl.config import settings
from ytdl.errors import UploadError

logger = logging.getLogger(__name__)


def get_r2_client():
    """Get boto3 S3 client configured for R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )


def upload_file(local_path: Path, object_key: str) -> str:
    """
    Upload a file to R2.

    Args:
        local_path: Path to the local file
        object_key: Key (path) in R2 bucket

    Returns:
        The object key

    Raises:
        UploadError: If upload fails
    """
    client = get_r2_client()

    try:
        client.upload_file(
            str(local_path),
            settings.r2_bucket_name,
            object_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        logger.info(f"Uploaded {local_path} to R2 as {object_key}")
        return object_key
    except ClientError as e:
        logger.error(f"Failed to upload {local_path} to R2: {e}")
        raise UploadError(f"Upload failed: {e}") from e


def generate_presigned_url(object_key: str, expiry_minutes: int | None = None) -> tuple[str, datetime]:
    """
    Generate a presigned URL for downloading a file from R2.

    Args:
        object_key: Key (path) in R2 bucket
        expiry_minutes: URL expiry time in minutes (default from settings)

    Returns:
        Tuple of (presigned URL, expiry datetime)

    Raises:
        UploadError: If URL generation fails
    """
    if expiry_minutes is None:
        expiry_minutes = settings.url_expiry_minutes

    client = get_r2_client()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

    try:
        # If custom public URL is configured, use it
        if settings.r2_public_url:
            url = f"{settings.r2_public_url.rstrip('/')}/{object_key}"
            return url, expires_at

        # Otherwise generate presigned URL
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.r2_bucket_name,
                "Key": object_key,
            },
            ExpiresIn=expiry_minutes * 60,
        )
        return url, expires_at
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {object_key}: {e}")
        raise UploadError(f"Failed to generate download URL: {e}") from e


def delete_file(object_key: str) -> None:
    """
    Delete a file from R2.

    Args:
        object_key: Key (path) in R2 bucket
    """
    client = get_r2_client()

    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=object_key)
        logger.info(f"Deleted {object_key} from R2")
    except ClientError as e:
        logger.warning(f"Failed to delete {object_key} from R2: {e}")
