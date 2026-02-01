# iPhone YouTube 影片下載器

透過 Apple 捷徑將 YouTube 影片直接下載到 iPhone 相簿的後端 API。

[English](README.md)

## 架構

```
iPhone 捷徑 → Railway/VPS → Redis → Worker → Cloudflare R2
                                                   ↓
                                           Signed URL → iPhone
```

## 部署方式

參考 [Railway 部署教學](docs/deployment-railway.md)

## 快速開始（Railway）

1. Fork 這個專案到你的 GitHub
2. 前往 [railway.app](https://railway.app) 從 GitHub 建立新專案
3. 新增 Redis 服務
4. 設定環境變數（參考 [Railway 教學](docs/deployment-railway.md)）
5. 部署完成！

## 本地測試

```bash
# 安裝依賴
uv sync

# 執行測試
make test
```

## API 說明

### 認證

所有請求需要 `X-API-Token` header：

```
X-API-Token: your-api-token
```

### POST /jobs

建立下載任務。

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
| quality | string | 否 | `480`、`720`、`1080` 或 `best`（預設：`720`） |

**回應 (200)：**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### GET /jobs/{job_id}

查詢任務狀態。

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

## 本地開發

### 前置需求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker（用於 Redis）
- ffmpeg

### 指令

```bash
make install     # 安裝依賴
make test        # 完整測試
make test-quick  # 快速測試（不下載）
make dev         # 啟動開發伺服器
make clean       # 停止服務並清理
```

## 文件

- [Railway 部署教學](docs/deployment-railway.md)
- [iPhone 捷徑設置](docs/iphone-shortcut.md)

## 授權

MIT
