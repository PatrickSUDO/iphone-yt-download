# YouTube Video Downloader for iPhone

A backend API for downloading YouTube videos directly to your iPhone's photo album via Apple Shortcuts.

[繁體中文說明](README.zh-TW.md)

## Architecture

```
iPhone Shortcut → Caddy (TLS) → FastAPI → Redis Queue → Worker → Cloudflare R2
                                                                      ↓
                                                              Signed URL → iPhone
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Cloudflare R2 bucket with API credentials
- A domain name (for HTTPS)

### 1. Clone and Configure

```bash
git clone <repo-url>
cd iphone-yt-download

# Copy and edit environment variables
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Required
API_TOKEN=your-secure-random-token
R2_ACCOUNT_ID=your-cloudflare-account-id
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=ytdl-videos
DOMAIN=your-domain.com
```

### 2. Deploy

```bash
docker compose up -d
```

### 3. Set Up iPhone Shortcut

See [iPhone Shortcut Setup Guide](docs/iphone-shortcut.md)

## API Reference

### Authentication

All requests require the `X-API-Token` header:

```
X-API-Token: your-api-token
```

### POST /jobs

Create a new download job.

**Request:**

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "quality": "720"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| url | string | Yes | YouTube video URL |
| quality | string | No | Video quality: `480`, `720`, `1080`, or `best` (default: `720`) |

**Response (200):**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### GET /jobs/{job_id}

Get job status.

**Response (running):**

```json
{
  "job_id": "uuid",
  "status": "running",
  "progress": {
    "stage": "downloading",
    "pct": 42
  }
}
```

**Response (done):**

```json
{
  "job_id": "uuid",
  "status": "done",
  "download_url": "https://...",
  "expires_at": "2026-02-01T12:34:56Z",
  "filename": "video.mp4"
}
```

**Response (error):**

```json
{
  "job_id": "uuid",
  "status": "error",
  "error_code": "DOWNLOAD_FAILED",
  "message": "Error description"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| INVALID_URL | Invalid or unsupported URL |
| UPSTREAM_FAILURE | YouTube temporarily unavailable |
| DOWNLOAD_FAILED | Download failed |
| MERGE_FAILED | Failed to merge video/audio |
| UPLOAD_FAILED | Failed to upload to R2 |
| UNAUTHORIZED | Invalid API token |
| RATE_LIMITED | Too many requests |
| JOB_NOT_FOUND | Job not found |

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Redis
- ffmpeg
- aria2 (optional, for faster downloads)

### Setup

```bash
# Install dependencies
uv sync

# Start Redis
docker run -d -p 6379:6379 redis:alpine

# Copy and edit .env
cp .env.example .env

# Start API server
uv run uvicorn ytdl.main:app --reload

# In another terminal, start worker
uv run rq worker --url redis://localhost:6379/0
```

### Test

```bash
# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "X-API-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720"}'

# Check status
curl http://localhost:8000/jobs/{job_id} \
  -H "X-API-Token: your-token"
```

## R2 Bucket Setup

1. Create a bucket in Cloudflare R2
2. Create an API token with read/write permissions
3. (Recommended) Set up lifecycle rules to auto-delete files after 3-7 days

## License

MIT
