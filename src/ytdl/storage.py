"""Storage operations for both local and Cloudflare R2."""

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ytdl.config import StorageMode, settings
from ytdl.errors import UploadError

logger = logging.getLogger(__name__)


# --- Local Storage ---


def _ensure_local_storage_dir() -> Path:
    """Ensure local storage directory exists."""
    storage_dir = Path(settings.local_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def _upload_local(local_path: Path, object_key: str) -> str:
    """Copy file to local storage directory."""
    storage_dir = _ensure_local_storage_dir()

    # Create subdirectories if needed
    dest_path = storage_dir / object_key
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy file
    shutil.copy2(local_path, dest_path)
    logger.info(f"Copied {local_path} to {dest_path}")
    return object_key


def _generate_local_url(object_key: str, expiry_minutes: int) -> tuple[str, datetime]:
    """Generate URL for local file download."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    url = f"{settings.base_url.rstrip('/')}/downloads/{object_key}"
    return url, expires_at


def _delete_local(object_key: str) -> None:
    """Delete file from local storage."""
    storage_dir = _ensure_local_storage_dir()
    file_path = storage_dir / object_key
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted {file_path}")


# --- R2 Storage ---


def _get_r2_client():
    """Get boto3 S3 client configured for R2."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",  # Required for Cloudflare R2
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )


def _upload_r2(local_path: Path, object_key: str) -> str:
    """Upload file to R2."""
    from botocore.exceptions import ClientError

    client = _get_r2_client()
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


def _generate_r2_url(object_key: str, expiry_minutes: int) -> tuple[str, datetime]:
    """Generate presigned URL for R2."""
    from botocore.exceptions import ClientError

    client = _get_r2_client()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

    try:
        if settings.r2_public_url:
            url = f"{settings.r2_public_url.strip().rstrip('/')}/{object_key}"
            return url, expires_at

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


def _delete_r2(object_key: str) -> None:
    """Delete file from R2."""
    from botocore.exceptions import ClientError

    client = _get_r2_client()
    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=object_key)
        logger.info(f"Deleted {object_key} from R2")
    except ClientError as e:
        logger.warning(f"Failed to delete {object_key} from R2: {e}")


# --- Public API ---


def upload_file(local_path: Path, object_key: str) -> str:
    """
    Upload a file to storage.

    Args:
        local_path: Path to the local file
        object_key: Key (path) in storage

    Returns:
        The object key

    Raises:
        UploadError: If upload fails
    """
    if settings.storage_mode == StorageMode.R2:
        return _upload_r2(local_path, object_key)
    else:
        return _upload_local(local_path, object_key)


def generate_presigned_url(object_key: str, expiry_minutes: int | None = None) -> tuple[str, datetime]:
    """
    Generate a URL for downloading a file.

    Args:
        object_key: Key (path) in storage
        expiry_minutes: URL expiry time in minutes (default from settings)

    Returns:
        Tuple of (URL, expiry datetime)
    """
    if expiry_minutes is None:
        expiry_minutes = settings.url_expiry_minutes

    if settings.storage_mode == StorageMode.R2:
        return _generate_r2_url(object_key, expiry_minutes)
    else:
        return _generate_local_url(object_key, expiry_minutes)


def delete_file(object_key: str) -> None:
    """
    Delete a file from storage.

    Args:
        object_key: Key (path) in storage
    """
    if settings.storage_mode == StorageMode.R2:
        _delete_r2(object_key)
    else:
        _delete_local(object_key)
