"""Error codes and exceptions for the YouTube downloader."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Error codes returned by the API."""

    INVALID_URL = "INVALID_URL"
    UPSTREAM_FAILURE = "UPSTREAM_FAILURE"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    MERGE_FAILED = "MERGE_FAILED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


ERROR_MESSAGES = {
    ErrorCode.INVALID_URL: "Invalid or unsupported URL. Only YouTube URLs are supported.",
    ErrorCode.UPSTREAM_FAILURE: "YouTube is temporarily unavailable. Please try again later.",
    ErrorCode.DOWNLOAD_FAILED: "Failed to download the video. Please try again.",
    ErrorCode.MERGE_FAILED: "Failed to merge video and audio streams.",
    ErrorCode.UPLOAD_FAILED: "Failed to upload the processed video.",
    ErrorCode.UNAUTHORIZED: "Invalid or missing API token.",
    ErrorCode.RATE_LIMITED: "Too many requests. Please slow down.",
    ErrorCode.JOB_NOT_FOUND: "Job not found.",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred.",
}


class YTDLError(Exception):
    """Base exception for YTDL errors."""

    def __init__(self, code: ErrorCode, message: str | None = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "Unknown error")
        super().__init__(self.message)


class InvalidURLError(YTDLError):
    """Raised when URL is invalid or not supported."""

    def __init__(self, message: str | None = None):
        super().__init__(ErrorCode.INVALID_URL, message)


class DownloadError(YTDLError):
    """Raised when download fails."""

    def __init__(self, code: ErrorCode = ErrorCode.DOWNLOAD_FAILED, message: str | None = None):
        super().__init__(code, message)


class UploadError(YTDLError):
    """Raised when upload to R2 fails."""

    def __init__(self, message: str | None = None):
        super().__init__(ErrorCode.UPLOAD_FAILED, message)
