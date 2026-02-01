# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube video downloader backend designed to work with iPhone Shortcuts. Users share a YouTube URL via iOS Share Sheet → Shortcut calls the API → video is downloaded and saved to their photo album.

## Architecture

```
iPhone Shortcut → Caddy (TLS) → FastAPI → Redis Queue → Worker → Cloudflare R2
                                                                      ↓
                                                              Signed URL → iPhone
```

## Build/Run Commands

```bash
# Install dependencies
uv sync

# Run API server (development)
uv run uvicorn ytdl.main:app --reload

# Run worker (development)
uv run rq worker --url redis://localhost:6379/0

# Production deployment
docker compose up -d

# Lint
uv run ruff check src/
uv run ruff format src/
```

## Project Structure

- `src/ytdl/main.py` - FastAPI application entry point
- `src/ytdl/api.py` - API routes (POST /jobs, GET /jobs/{id})
- `src/ytdl/worker.py` - RQ worker job processor
- `src/ytdl/downloader.py` - yt-dlp download logic
- `src/ytdl/storage.py` - Cloudflare R2 operations
- `src/ytdl/config.py` - Environment configuration (pydantic-settings)
- `src/ytdl/models.py` - Pydantic request/response schemas
- `src/ytdl/errors.py` - Error codes and exceptions

## Key Patterns

- **Job Queue**: Uses Redis + RQ for async job processing
- **Storage**: Cloudflare R2 with presigned URLs (30 min TTL default)
- **Authentication**: Simple API token via `X-API-Token` header
- **Download**: yt-dlp with aria2c (if available) for parallel downloads
- **Video Processing**: ffmpeg remux only (no re-encoding) for speed

## Error Codes

`INVALID_URL`, `UPSTREAM_FAILURE`, `DOWNLOAD_FAILED`, `MERGE_FAILED`, `UPLOAD_FAILED`, `UNAUTHORIZED`, `RATE_LIMITED`, `JOB_NOT_FOUND`

## Environment Variables

Required: `API_TOKEN`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

Optional: `REDIS_URL`, `R2_PUBLIC_URL`, `URL_EXPIRY_MINUTES`, `RATE_LIMIT_PER_MINUTE`, `MAX_CONCURRENT_JOBS`
