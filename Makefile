.PHONY: install dev api worker test test-quick clean stop redis-start redis-stop help

# Configuration
TEST_URL ?= https://www.youtube.com/watch?v=5NM6taoljdM
TEST_QUALITY ?= 720
API_TOKEN ?= test-token
REDIS_CONTAINER ?= ytdl-redis

help:
	@echo "YouTube Downloader - Available commands:"
	@echo ""
	@echo "  make install     - Install dependencies with uv"
	@echo "  make dev         - Start API server in development mode"
	@echo "  make api         - Start API server (background)"
	@echo "  make worker      - Start RQ worker (background)"
	@echo "  make test        - Run full integration test"
	@echo "  make test-quick  - Run quick test (info only, no download)"
	@echo "  make stop        - Stop all services"
	@echo "  make clean       - Stop services and clean downloads"
	@echo ""

install:
	uv sync

# Start Redis container
redis-start:
	@docker start $(REDIS_CONTAINER) 2>/dev/null || \
		docker run -d --name $(REDIS_CONTAINER) -p 6379:6379 redis:alpine
	@echo "Redis started"

redis-stop:
	@docker stop $(REDIS_CONTAINER) 2>/dev/null || true
	@echo "Redis stopped"

# Development server (foreground)
dev: redis-start
	uv run uvicorn ytdl.main:app --reload --host 0.0.0.0 --port 8000

# Start API server in background
api: redis-start
	@pkill -f "uvicorn ytdl" 2>/dev/null || true
	@uv run uvicorn ytdl.main:app --host 0.0.0.0 --port 8000 > /tmp/ytdl-api.log 2>&1 &
	@sleep 2
	@curl -sf http://localhost:8000/health > /dev/null && echo "API server started on http://localhost:8000" || echo "Failed to start API server"

# Start worker in background
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES is required on macOS to prevent fork() crash
worker: redis-start
	@pkill -f "rq worker" 2>/dev/null || true
	@OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run rq worker --url redis://localhost:6379/0 > /tmp/ytdl-worker.log 2>&1 &
	@sleep 1
	@echo "Worker started"

# Stop all services
stop:
	@pkill -f "uvicorn ytdl" 2>/dev/null || true
	@pkill -f "rq worker" 2>/dev/null || true
	@echo "Services stopped"

# Clean downloads and stop services
clean: stop
	@rm -rf ./downloads/*
	@rm -rf /tmp/ytdl-downloads/*
	@echo "Cleaned up"

# Quick test - just extract video info
test-quick:
	@echo "Testing yt-dlp with: $(TEST_URL)"
	@uv run python -c "\
import yt_dlp; \
ydl = yt_dlp.YoutubeDL({'quiet': True}); \
info = ydl.extract_info('$(TEST_URL)', download=False); \
print(f'Title: {info[\"title\"]}'); \
print(f'Duration: {info[\"duration\"]}s'); \
print(f'Formats: {len(info[\"formats\"])} available')"
	@echo "Quick test passed!"

# Full integration test
test: api worker
	@echo ""
	@echo "========================================="
	@echo "Starting integration test"
	@echo "URL: $(TEST_URL)"
	@echo "Quality: $(TEST_QUALITY)"
	@echo "========================================="
	@echo ""
	@# Create job
	@JOB_ID=$$(curl -sf -X POST http://localhost:8000/jobs \
		-H "X-API-Token: $(API_TOKEN)" \
		-H "Content-Type: application/json" \
		-d '{"url": "$(TEST_URL)", "quality": "$(TEST_QUALITY)"}' | \
		python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])") && \
	echo "Job created: $$JOB_ID" && \
	echo "" && \
	echo "Polling for completion (max 5 minutes)..." && \
	for i in $$(seq 1 100); do \
		RESULT=$$(curl -sf "http://localhost:8000/jobs/$$JOB_ID" -H "X-API-Token: $(API_TOKEN)"); \
		STATUS=$$(echo "$$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))"); \
		PROGRESS=$$(echo "$$RESULT" | python3 -c "import sys,json; p=json.load(sys.stdin).get('progress'); print(f\"{p['stage']} {p['pct']}%\" if p else 'waiting')" 2>/dev/null || echo "waiting"); \
		printf "\r[%3d] Status: %-10s Progress: %-20s" $$i "$$STATUS" "$$PROGRESS"; \
		if [ "$$STATUS" = "done" ]; then \
			echo ""; \
			echo ""; \
			echo "=========================================" ; \
			echo "SUCCESS!" ; \
			echo "=========================================" ; \
			echo "$$RESULT" | python3 -m json.tool; \
			DOWNLOAD_URL=$$(echo "$$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('download_url',''))"); \
			echo ""; \
			echo "Download URL: $$DOWNLOAD_URL"; \
			break; \
		elif [ "$$STATUS" = "error" ]; then \
			echo ""; \
			echo ""; \
			echo "=========================================" ; \
			echo "FAILED!" ; \
			echo "=========================================" ; \
			echo "$$RESULT" | python3 -m json.tool; \
			break; \
		fi; \
		sleep 3; \
	done
	@echo ""
	@echo "Stopping services..."
	@$(MAKE) stop --no-print-directory
	@echo "Test complete!"
