# YouTube Video Downloader for iPhone

A backend API for downloading YouTube videos directly to your iPhone's photo album via Apple Shortcuts.

[繁體中文說明](README.zh-TW.md)

## Architecture

```
iPhone Shortcut → Railway/VPS → Redis → Worker → Cloudflare R2
                                                       ↓
                                               Signed URL → iPhone
```

## Deployment Options

| Method | Difficulty | Cost | Best For |
|--------|------------|------|----------|
| [Railway](docs/deployment-railway.md) | ⭐ Easy | ~$5/mo | Quick setup, light usage |
| [Hetzner VPS](docs/deployment.md) | Medium | ~$5/mo | Heavy usage, predictable cost |

## Quick Start (Railway)

1. Fork this repo to your GitHub
2. Go to [railway.app](https://railway.app) and create new project from GitHub
3. Add Redis service
4. Set environment variables (see [Railway Guide](docs/deployment-railway.md))
5. Deploy!

## Quick Start (Local Testing)

```bash
# Install dependencies
uv sync

# Run test
make test
```

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
| quality | string | No | `480`, `720`, `1080`, or `best` (default: `720`) |

**Response (200):**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### GET /jobs/{job_id}

Get job status.

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

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker (for Redis)
- ffmpeg

### Commands

```bash
make install     # Install dependencies
make test        # Run full integration test
make test-quick  # Quick test (no download)
make dev         # Start dev server
make clean       # Stop services and cleanup
```

## Documentation

- [Railway Deployment](docs/deployment-railway.md) - Recommended
- [Hetzner VPS Deployment](docs/deployment.md)
- [iPhone Shortcut Setup](docs/iphone-shortcut.md)

## License

MIT
