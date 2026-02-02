"""Cobalt API fallback downloader for when yt-dlp fails."""

import logging
import re
from collections.abc import Callable
from pathlib import Path

import httpx

from ytdl.config import settings
from ytdl.errors import DownloadError, ErrorCode

logger = logging.getLogger(__name__)

# Cobalt API quality mapping (yt-dlp uses 480/720/1080, Cobalt uses "720" string format)
QUALITY_MAP = {
    "480": "480",
    "720": "720",
    "1080": "1080",
    "best": "max",
}


def _sanitize_filename(title: str) -> str:
    """Sanitize video title for use as filename."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    sanitized = re.sub(r"[\s_]+", "_", sanitized)
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized.strip("_")


async def _fetch_cobalt_download_url(url: str, quality: str) -> str:
    """
    Call Cobalt API to get download URL.

    Args:
        url: YouTube video URL
        quality: Video quality (480, 720, 1080, best)

    Returns:
        Direct download URL from Cobalt

    Raises:
        DownloadError: If Cobalt API fails
    """
    cobalt_quality = QUALITY_MAP.get(quality, "720")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Add API key if configured
    if settings.cobalt_api_key:
        headers["Authorization"] = f"Api-Key {settings.cobalt_api_key}"

    payload = {
        "url": url,
        "videoQuality": cobalt_quality,
        "filenameStyle": "basic",
    }

    logger.info(f"Calling Cobalt API for: {url} at quality {cobalt_quality}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                settings.cobalt_api_url,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Cobalt API error: {response.status_code} - {response.text}")
                raise DownloadError(
                    ErrorCode.DOWNLOAD_FAILED,
                    f"Cobalt API returned status {response.status_code}",
                )

            data = response.json()
            status = data.get("status")

            if status == "error":
                error_code = data.get("error", {}).get("code", "unknown")
                logger.error(f"Cobalt API error: {error_code}")
                raise DownloadError(
                    ErrorCode.DOWNLOAD_FAILED,
                    f"Cobalt API error: {error_code}",
                )

            if status not in ("tunnel", "redirect"):
                logger.error(f"Unexpected Cobalt status: {status}")
                raise DownloadError(
                    ErrorCode.DOWNLOAD_FAILED,
                    f"Unexpected Cobalt status: {status}",
                )

            download_url = data.get("url")
            if not download_url:
                raise DownloadError(
                    ErrorCode.DOWNLOAD_FAILED,
                    "Cobalt API did not return download URL",
                )

            logger.info(f"Cobalt API returned status: {status}")
            return download_url

        except httpx.RequestError as e:
            logger.error(f"Cobalt API request failed: {e}")
            raise DownloadError(
                ErrorCode.DOWNLOAD_FAILED,
                f"Cobalt API request failed: {e}",
            ) from e


async def _download_file(
    download_url: str,
    output_path: Path,
    progress_callback: Callable[[str, int], None] | None = None,
) -> None:
    """
    Download file from URL to local path.

    Args:
        download_url: URL to download from
        output_path: Local file path to save to
        progress_callback: Optional callback(stage, percentage)
    """
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        async with client.stream("GET", download_url) as response:
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size > 0:
                        pct = int(downloaded * 100 / total_size)
                        progress_callback("downloading", pct)


def download_with_cobalt(
    url: str,
    quality: str,
    output_dir: Path,
    progress_callback: Callable[[str, int], None] | None = None,
) -> Path:
    """
    Download a YouTube video using Cobalt API (synchronous wrapper).

    Args:
        url: YouTube video URL
        quality: Video quality (480, 720, 1080, best)
        output_dir: Directory to save the video
        progress_callback: Optional callback(stage, percentage)

    Returns:
        Path to the downloaded video file

    Raises:
        DownloadError: If download fails
    """
    import asyncio

    return asyncio.run(
        _download_with_cobalt_async(url, quality, output_dir, progress_callback)
    )


async def _download_with_cobalt_async(
    url: str,
    quality: str,
    output_dir: Path,
    progress_callback: Callable[[str, int], None] | None = None,
) -> Path:
    """
    Download a YouTube video using Cobalt API.

    Args:
        url: YouTube video URL
        quality: Video quality (480, 720, 1080, best)
        output_dir: Directory to save the video
        progress_callback: Optional callback(stage, percentage)

    Returns:
        Path to the downloaded video file

    Raises:
        DownloadError: If download fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Get download URL from Cobalt
        download_url = await _fetch_cobalt_download_url(url, quality)

        # Generate output filename
        # Extract video ID from URL for consistent naming
        video_id = _extract_video_id(url) or "video"
        output_path = output_dir / f"cobalt_{video_id}.mp4"

        logger.info(f"Downloading from Cobalt to: {output_path}")

        # Download the file
        await _download_file(download_url, output_path, progress_callback)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise DownloadError(
                ErrorCode.DOWNLOAD_FAILED,
                "Downloaded file is empty or missing",
            )

        logger.info(f"Cobalt download complete: {output_path}")
        return output_path

    except DownloadError:
        raise
    except Exception as e:
        logger.error(f"Cobalt download failed: {e}")
        raise DownloadError(
            ErrorCode.DOWNLOAD_FAILED,
            f"Cobalt download failed: {e}",
        ) from e


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def should_fallback_to_cobalt(error: Exception) -> bool:
    """
    Determine if we should try Cobalt fallback based on the error.

    Args:
        error: The exception from yt-dlp

    Returns:
        True if we should try Cobalt fallback
    """
    error_str = str(error).lower()

    # Bot detection / sign-in required errors
    bot_detection_patterns = [
        "sign in",
        "signin",
        "bot",
        "confirm you",
        "verify",
        "captcha",
        "unusual traffic",
        "blocked",
    ]

    for pattern in bot_detection_patterns:
        if pattern in error_str:
            logger.info(f"Detected bot/sign-in error, will try Cobalt fallback: {pattern}")
            return True

    return False
