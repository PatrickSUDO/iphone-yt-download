"""YouTube video downloader using yt-dlp."""

import base64
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import yt_dlp

from ytdl.config import settings
from ytdl.errors import DownloadError, ErrorCode

logger = logging.getLogger(__name__)


def sanitize_filename(title: str) -> str:
    """Sanitize video title for use as filename (ASCII only for URL compatibility)."""
    # Remove non-ASCII characters to avoid URL encoding issues
    sanitized = title.encode("ascii", "ignore").decode("ascii")
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*()&]', "", sanitized)
    # Replace multiple spaces/underscores with single underscore
    sanitized = re.sub(r"[\s_]+", "_", sanitized)
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    # Fallback if filename is empty after sanitization
    if not sanitized.strip("_"):
        sanitized = "video"
    return sanitized.strip("_")


def get_format_selector(quality: str) -> str:
    """
    Get yt-dlp format selector string for requested quality.

    Uses separate video + audio streams for better compatibility,
    especially with YouTube Shorts and restricted videos.
    """
    quality_map = {
        "480": "bv*[height<=480]+ba/best[height<=480]/best",
        "720": "bv*[height<=720]+ba/best[height<=720]/best",
        "1080": "bv*[height<=1080]+ba/best[height<=1080]/best",
        "best": "bv*+ba/best",
    }
    return quality_map.get(quality, "bv*[height<=720]+ba/best[height<=720]/best")


def get_progressive_format_selector(quality: str) -> str:
    """
    Get a progressive MP4-first format selector.

    This avoids DASH/HLS manifests and prefers single-file MP4 formats
    such as 18/22 that are faster and less likely to hit YouTube's
    throttled adaptive-stream path on datacenter IPs.
    """
    quality_map = {
        "480": "best[ext=mp4][height<=480]/18",
        "720": "best[ext=mp4][height<=720]/22/18",
        "1080": "best[ext=mp4][height<=1080]/22/18",
        "best": "best[ext=mp4]/22/18",
    }
    return quality_map.get(quality, "best[ext=mp4][height<=720]/22/18")


def should_retry_with_adaptive_formats(error_message: str) -> bool:
    """Return True when the progressive MP4 fast path has no usable format."""
    message = error_message.lower()
    retry_patterns = (
        "requested format is not available",
        "requested format not available",
        "no suitable format",
        "no video formats found",
        "only images are available for download",
    )
    return any(pattern in message for pattern in retry_patterns)


def build_ydl_opts(
    quality: str,
    output_dir: Path,
    progress_hook,
    *,
    progressive_only: bool,
) -> dict:
    """Build yt-dlp options for the selected download strategy."""
    ydl_opts = {
        "format": (
            get_progressive_format_selector(quality)
            if progressive_only
            else get_format_selector(quality)
        ),
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 5,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # Prefer remux over re-encode
        "postprocessor_args": {
            "ffmpeg": ["-c", "copy"],
        },
    }

    if progressive_only:
        # Skip DASH/HLS manifest extraction so yt-dlp goes straight to direct MP4s.
        ydl_opts["extractor_args"] = {"youtube": ["skip=dash,hls"]}
    else:
        # Prefer h264/aac for iPhone compatibility on the adaptive-stream fallback.
        ydl_opts["format_sort"] = ["vcodec:h264", "acodec:aac", "ext:mp4:m4a"]

    return ydl_opts


def check_aria2c_available() -> bool:
    """Check if aria2c is available."""
    return shutil.which("aria2c") is not None


def get_cookies_file() -> Path | None:
    """Get cookies file path, creating from base64 env var if needed."""
    # If configured, pass cookies through to yt-dlp.
    if not settings.youtube_cookies_base64:
        return None

    try:
        cookies_content = base64.b64decode(settings.youtube_cookies_base64).decode("utf-8")
        cookies_path = Path(tempfile.gettempdir()) / "youtube_cookies.txt"
        cookies_path.write_text(cookies_content)
        logger.info(f"Loaded YouTube cookies: {len(cookies_content.strip().split(chr(10)))} lines")
        return cookies_path
    except Exception as e:
        logger.warning(f"Failed to decode cookies: {e}")
        return None


def download_video(
    url: str,
    quality: str,
    output_dir: Path,
    progress_callback: Callable[[str, int], None] | None = None,
) -> Path:
    """
    Download a YouTube video.

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

    # Progress hook for yt-dlp
    def progress_hook(d):
        if progress_callback and d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int(downloaded * 100 / total)
                progress_callback("downloading", pct)
        elif progress_callback and d["status"] == "finished":
            progress_callback("processing", 0)

    def run_download(*, progressive_only: bool) -> Path:
        ydl_opts = build_ydl_opts(
            quality,
            output_dir,
            progress_hook,
            progressive_only=progressive_only,
        )

        # Add cookies if available
        cookies_file = get_cookies_file()
        if cookies_file:
            ydl_opts["cookiefile"] = str(cookies_file)

        # Use aria2c if available for faster downloads
        if check_aria2c_available():
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = {
                "aria2c": [
                    f"-x{settings.concurrent_fragments}",
                    f"-s{settings.concurrent_fragments}",
                    "-k1M",
                    "--file-allocation=none",
                ]
            }
            logger.info("Using aria2c for download")
        else:
            logger.info("aria2c not found, using built-in downloader")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise DownloadError(ErrorCode.UPSTREAM_FAILURE, "Could not extract video info")

            video_id = info.get("id", "video")
            video_title = info.get("title", "video")

            logger.info(
                "Downloaded %s (%s) via %s path",
                video_title,
                video_id,
                "progressive" if progressive_only else "adaptive",
            )

            output_files = list(output_dir.glob(f"{video_id}.*"))

            if not output_files:
                raise DownloadError(ErrorCode.DOWNLOAD_FAILED, "Output file not found after download")

            # Prefer mp4, otherwise take first file
            output_file = None
            for f in output_files:
                if f.suffix.lower() == ".mp4":
                    output_file = f
                    break
            if not output_file:
                output_file = output_files[0]

            # Rename to sanitized title
            sanitized_name = sanitize_filename(video_title)
            final_path = output_dir / f"{sanitized_name}.mp4"

            # If not already mp4, remux with ffmpeg
            if output_file.suffix.lower() != ".mp4":
                logger.info(f"Remuxing {output_file} to mp4")
                if progress_callback:
                    progress_callback("processing", 50)

                remux_cmd = [
                    "ffmpeg",
                    "-i", str(output_file),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    "-y",
                    str(final_path),
                ]
                result = subprocess.run(
                    remux_cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error(f"ffmpeg remux failed: {result.stderr}")
                    raise DownloadError(ErrorCode.MERGE_FAILED, "Failed to remux video")

                # Clean up original file
                output_file.unlink(missing_ok=True)
            else:
                # Just rename
                output_file.rename(final_path)

            logger.info(f"Download complete: {final_path}")
            return final_path

    try:
        return run_download(progressive_only=True)
    except yt_dlp.utils.DownloadError as e:
        logger.warning(f"Progressive download path failed: {e}")
        if not should_retry_with_adaptive_formats(str(e)):
            if "unavailable" in str(e).lower() or "private" in str(e).lower():
                raise DownloadError(ErrorCode.UPSTREAM_FAILURE, str(e)) from e
            raise DownloadError(ErrorCode.DOWNLOAD_FAILED, str(e)) from e

        logger.info("Retrying with adaptive YouTube formats")

    try:
        return run_download(progressive_only=False)
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        if "unavailable" in str(e).lower() or "private" in str(e).lower():
            raise DownloadError(ErrorCode.UPSTREAM_FAILURE, str(e)) from e
        raise DownloadError(ErrorCode.DOWNLOAD_FAILED, str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected download error: {e}")
        if isinstance(e, DownloadError):
            raise
        raise DownloadError(ErrorCode.DOWNLOAD_FAILED, str(e)) from e
