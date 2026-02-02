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
    """Sanitize video title for use as filename."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    # Replace multiple spaces/underscores with single underscore
    sanitized = re.sub(r"[\s_]+", "_", sanitized)
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized.strip("_")


def get_format_selector(quality: str) -> str:
    """
    Get yt-dlp format selector string for requested quality.

    Uses separate video + audio streams for better compatibility,
    especially with YouTube Shorts and restricted videos.
    """
    quality_map = {
        "480": "bv*[height<=480]+ba/best",
        "720": "bv*[height<=720]+ba/best",
        "1080": "bv*[height<=1080]+ba/best",
        "best": "bv*+ba/best",
    }
    return quality_map.get(quality, "bv*[height<=720]+ba/best")


def check_aria2c_available() -> bool:
    """Check if aria2c is available."""
    return shutil.which("aria2c") is not None


def get_cookies_file() -> Path | None:
    """Get cookies file path, creating from base64 env var if needed."""
    # Cookies disabled - Railway IP works without them
    # If needed in future, set YOUTUBE_COOKIES_BASE64 env var
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

    # Configure yt-dlp options
    ydl_opts = {
        "format": get_format_selector(quality),
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        # Prefer remux over re-encode
        "postprocessor_args": {
            "ffmpeg": ["-c", "copy"],
        },
    }

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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get video ID
            info = ydl.extract_info(url, download=False)
            if not info:
                raise DownloadError(ErrorCode.UPSTREAM_FAILURE, "Could not extract video info")

            video_id = info.get("id", "video")
            video_title = info.get("title", "video")

            # Download the video
            logger.info(f"Downloading: {video_title} ({video_id})")
            ydl.download([url])

            # Find the output file
            output_pattern = output_dir / f"{video_id}.*"
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
