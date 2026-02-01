"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ytdl.api import router
from ytdl.errors import ERROR_MESSAGES, ErrorCode
from ytdl.models import ErrorResponse

app = FastAPI(
    title="YouTube Downloader API",
    description="Backend API for downloading YouTube videos to iPhone via Shortcuts",
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with custom error response."""
    # Check if it's a URL validation error
    for error in exc.errors():
        if "url" in error.get("loc", []):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error_code=ErrorCode.INVALID_URL,
                    message=str(error.get("msg", ERROR_MESSAGES[ErrorCode.INVALID_URL])),
                ).model_dump(),
            )

    # Generic validation error
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error_code=ErrorCode.INVALID_URL,
            message=str(exc.errors()[0].get("msg", "Invalid request")),
        ).model_dump(),
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)
