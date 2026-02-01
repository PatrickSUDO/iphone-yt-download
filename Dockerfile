FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY start.sh ./

# Make start script executable
RUN chmod +x start.sh

# Install dependencies
RUN uv sync --frozen --no-dev

# Create directories
RUN mkdir -p /app/downloads /tmp/ytdl-downloads

# Expose port (Railway uses $PORT)
EXPOSE 8000

# Run both API and Worker
CMD ["./start.sh"]
