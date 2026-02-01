# iPhone YouTube 影片下載器

透過 Apple 捷徑將 YouTube 影片直接下載到 iPhone 相簿的後端 API。

[English](README.md)

## 架構

```
iPhone 捷徑 → Caddy (TLS) → FastAPI → Redis 佇列 → Worker → Cloudflare R2
                                                                  ↓
                                                          Signed URL → iPhone
```

## 快速開始

### 前置需求

- Docker & Docker Compose
- Cloudflare R2 儲存桶與 API 憑證
- 網域名稱（用於 HTTPS）

### 1. 複製並設定

```bash
git clone <repo-url>
cd iphone-yt-download

# 複製並編輯環境變數
cp .env.example .env
```

編輯 `.env` 設定：

```env
# 必填
API_TOKEN=你的安全隨機token
R2_ACCOUNT_ID=你的cloudflare帳號id
R2_ACCESS_KEY_ID=你的r2存取金鑰
R2_SECRET_ACCESS_KEY=你的r2密鑰
R2_BUCKET_NAME=ytdl-videos
DOMAIN=your-domain.com
```

### 2. 部署

```bash
docker compose up -d
```

### 3. 設定 iPhone 捷徑

參考 [iPhone 捷徑設置教學](docs/iphone-shortcut.md)

## API 說明

### 認證

所有請求需要 `X-API-Token` header：

```
X-API-Token: your-api-token
```

### POST /jobs

建立新的下載任務。

**請求：**

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "quality": "720"
}
```

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| url | string | 是 | YouTube 影片網址 |
| quality | string | 否 | 影片品質：`480`、`720`、`1080` 或 `best`（預設：`720`） |

**回應 (200)：**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### GET /jobs/{job_id}

查詢任務狀態。

**回應（處理中）：**

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

**回應（完成）：**

```json
{
  "job_id": "uuid",
  "status": "done",
  "download_url": "https://...",
  "expires_at": "2026-02-01T12:34:56Z",
  "filename": "video.mp4"
}
```

**回應（錯誤）：**

```json
{
  "job_id": "uuid",
  "status": "error",
  "error_code": "DOWNLOAD_FAILED",
  "message": "錯誤描述"
}
```

### 錯誤碼

| 錯誤碼 | 說明 |
|--------|------|
| INVALID_URL | 無效或不支援的網址 |
| UPSTREAM_FAILURE | YouTube 暫時無法存取 |
| DOWNLOAD_FAILED | 下載失敗 |
| MERGE_FAILED | 影音合併失敗 |
| UPLOAD_FAILED | 上傳至 R2 失敗 |
| UNAUTHORIZED | API Token 無效 |
| RATE_LIMITED | 請求過於頻繁 |
| JOB_NOT_FOUND | 找不到任務 |

## 本地開發

### 前置需求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Redis
- ffmpeg
- aria2（選用，可加速下載）

### 設定

```bash
# 安裝依賴
uv sync

# 啟動 Redis
docker run -d -p 6379:6379 redis:alpine

# 複製並編輯 .env
cp .env.example .env

# 啟動 API 伺服器
uv run uvicorn ytdl.main:app --reload

# 在另一個終端機啟動 worker
uv run rq worker --url redis://localhost:6379/0
```

### 測試

```bash
# 建立任務
curl -X POST http://localhost:8000/jobs \
  -H "X-API-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720"}'

# 查詢狀態
curl http://localhost:8000/jobs/{job_id} \
  -H "X-API-Token: your-token"
```

## R2 儲存桶設定

1. 在 Cloudflare R2 建立儲存桶
2. 建立具有讀寫權限的 API Token
3. （建議）設定生命週期規則，自動刪除 3-7 天前的檔案

## 授權條款

MIT
