# Railway 部署教學

本文件說明如何將 YouTube 下載器部署到 Railway，搭配 Cloudflare R2 儲存。

---

## 架構

```
iPhone 捷徑 → Railway (API + Worker) → Cloudflare R2 → iPhone
```

---

## 第一部分：Cloudflare R2 設定

### 1. 建立 R2 Bucket

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 左側選單點選 **R2 Object Storage**
3. 點選 **Create bucket**
4. 輸入名稱：`ytdl-videos`
5. 點選 **Create bucket**

### 2. 建立 API Token

1. 在 R2 頁面，點選 **Manage R2 API Tokens**
2. 點選 **Create API token**
3. 設定：
   - Token name: `ytdl-railway`
   - Permissions: **Object Read & Write**
   - Specify bucket: 選擇 `ytdl-videos`
4. 點選 **Create API Token**
5. **複製並保存**：
   ```
   Access Key ID: xxxxxx
   Secret Access Key: xxxxxx
   ```

### 3. 取得 Account ID

在 Cloudflare Dashboard 右側找到 **Account ID**，複製保存。

### 4. 設定自動刪除（Lifecycle）

1. 進入 bucket → **Settings**
2. **Object lifecycle rules** → **Add rule**
3. 設定：
   - Rule name: `auto-delete`
   - Action: **Delete objects**
   - Days: `7`

---

## 第二部分：Railway 部署

### 1. 註冊 Railway

前往 [railway.app](https://railway.app) 註冊帳號（可用 GitHub 登入）

### 2. 建立新專案

1. 點選 **New Project**
2. 選擇 **Deploy from GitHub repo**
3. 選擇你的 `iphone-yt-download` 專案
4. Railway 會自動偵測 Dockerfile 並開始建構

### 3. 新增 Redis

1. 在專案中點選 **+ New**
2. 選擇 **Database** → **Add Redis**
3. Redis 會自動建立並連結

### 4. 設定環境變數

點選你的服務 → **Variables** → **New Variable**，加入以下變數：

| 變數名稱 | 值 | 說明 |
|----------|-----|------|
| `API_TOKEN` | `你的安全密碼` | API 認證用（建議 32+ 字元） |
| `STORAGE_MODE` | `r2` | 使用 R2 儲存 |
| `R2_ACCOUNT_ID` | `你的 Account ID` | Cloudflare Account ID |
| `R2_ACCESS_KEY_ID` | `你的 Access Key` | R2 API Key |
| `R2_SECRET_ACCESS_KEY` | `你的 Secret Key` | R2 API Secret |
| `R2_BUCKET_NAME` | `ytdl-videos` | Bucket 名稱 |
| `BASE_URL` | `https://你的.railway.app` | Railway 提供的網址 |

> 💡 `REDIS_URL` 會由 Railway 自動注入，不需手動設定

### 5. 取得公開網址

1. 點選服務 → **Settings**
2. 找到 **Networking** → **Generate Domain**
3. 會得到類似 `xxx.up.railway.app` 的網址
4. **記得回去更新 `BASE_URL` 環境變數**

### 6. 部署完成

Railway 會自動建構並部署。完成後可以測試：

```bash
curl https://你的網址.up.railway.app/health
# 應該回傳: {"status":"ok","storage_mode":"r2"}
```

---

## 第三部分：測試

```bash
# 建立下載任務
curl -X POST https://你的網址.up.railway.app/jobs \
  -H "X-API-Token: 你的API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720"}'

# 查詢狀態
curl https://你的網址.up.railway.app/jobs/回傳的job_id \
  -H "X-API-Token: 你的API_TOKEN"
```

---

## 費用估算

### Railway

| 項目 | 免費額度 | 超過後 |
|------|----------|--------|
| 執行時間 | $5/月 | 依用量計費 |
| RAM | 含在執行時間 | - |
| 流量 | 100GB/月 | $0.10/GB |

### Cloudflare R2

| 項目 | 免費額度 | 超過後 |
|------|----------|--------|
| 儲存 | 10GB/月 | $0.015/GB |
| 下載流量 | **無限免費** | - |

### 預估月費

輕度使用（每天 5 部影片）：**$0-5/月**

---

## 常用操作

### 查看日誌

Railway Dashboard → 你的服務 → **Logs**

### 重新部署

推送程式碼到 GitHub，Railway 會自動重新部署。

或在 Dashboard 點選 **Deploy** → **Redeploy**

### 暫停服務

Settings → **Remove Service**（會停止計費）

---

## 疑難排解

### 部署失敗

1. 檢查 **Build Logs** 找錯誤訊息
2. 確認 `Dockerfile` 和 `start.sh` 都已提交到 GitHub

### Worker 沒有執行

1. 檢查 Logs 是否有 "Starting worker..." 訊息
2. 確認 Redis 已正確連結（檢查 `REDIS_URL` 環境變數）

### R2 上傳失敗

1. 確認 R2 環境變數正確
2. 確認 `STORAGE_MODE=r2`
3. 檢查 R2 API Token 權限是否為 Read & Write

### 下載的影片無法存取

1. 確認 `BASE_URL` 設定為你的 Railway 公開網址
2. 對於 R2 儲存，download_url 會是 R2 的 presigned URL，應該可以直接存取

---

## 與 Hetzner 比較

| | Railway | Hetzner |
|---|---|---|
| 部署難度 | ⭐ 超簡單 | 需要 SSH |
| 月費 | ~$5（浮動） | €4.85（固定） |
| 維護 | 零維護 | 偶爾需要 |
| 適合 | 輕度使用 | 大量使用 |
