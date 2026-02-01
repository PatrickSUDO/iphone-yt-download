# 部署教學：Hetzner VPS + Cloudflare R2

本文件說明如何將 YouTube 下載器部署到 Hetzner VPS，並使用 Cloudflare R2 作為檔案儲存。

---

## 第一部分：Cloudflare R2 設定

### 1. 建立 R2 Bucket

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 左側選單點選 **R2 Object Storage**
3. 點選 **Create bucket**
4. 輸入名稱：`ytdl-videos`（或你喜歡的名稱）
5. 選擇地區（建議選離你 VPS 近的）
6. 點選 **Create bucket**

### 2. 建立 API Token

1. 在 R2 頁面，點選 **Manage R2 API Tokens**
2. 點選 **Create API token**
3. 設定：
   - Token name: `ytdl-worker`
   - Permissions: **Object Read & Write**
   - Specify bucket: 選擇 `ytdl-videos`
4. 點選 **Create API Token**
5. **重要！複製並保存這些資訊**：
   ```
   Access Key ID: xxxxxxxxxxxxxxxxxxxxxx
   Secret Access Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### 3. 取得 Account ID

1. 在 Cloudflare Dashboard 右側可以看到 **Account ID**
2. 複製保存

### 4. 設定 Lifecycle（自動刪除舊檔案）

1. 進入你的 bucket (`ytdl-videos`)
2. 點選 **Settings**
3. 找到 **Object lifecycle rules**
4. 點選 **Add rule**
5. 設定：
   - Rule name: `auto-delete`
   - Prefix: 留空（套用到所有檔案）
   - Action: **Delete objects**
   - Days after creation: `7`（或你想要的天數）

---

## 第二部分：Hetzner VPS 設定

### 1. 建立 VPS

1. 註冊/登入 [Hetzner Cloud](https://console.hetzner.cloud)
2. 點選 **Add Server**
3. 選擇配置：
   - **Location**: 選離你近的（如 Singapore）
   - **Image**: Ubuntu 24.04
   - **Type**: CPX11（2 vCPU, 2GB RAM）約 €4.85/月
   - **SSH Key**: 建議加入你的 SSH 公鑰
4. 點選 **Create & Buy now**
5. 記下伺服器 IP

### 2. 設定網域（DNS）

在你的網域 DNS 設定中加入 A 記錄：

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | ytdl（或 @） | 你的 VPS IP | Auto |

例如：`ytdl.yourdomain.com` → `123.45.67.89`

### 3. SSH 連線到 VPS

```bash
ssh root@你的VPS_IP
```

### 4. 安裝 Docker

```bash
# 更新系統
apt update && apt upgrade -y

# 安裝 Docker
curl -fsSL https://get.docker.com | sh

# 安裝 Docker Compose
apt install docker-compose-plugin -y

# 確認安裝
docker --version
docker compose version
```

### 5. 上傳專案檔案

在你的**本機**執行（不是 VPS）：

```bash
# 建立遠端目錄
ssh root@你的VPS_IP "mkdir -p /opt/ytdl"

# 上傳專案檔案（排除不需要的目錄）
rsync -avz --exclude '.venv' --exclude 'downloads' --exclude '__pycache__' \
  ./ root@你的VPS_IP:/opt/ytdl/
```

或者手動上傳需要的檔案：

```bash
scp -r docker/ docker-compose.yml pyproject.toml uv.lock src/ \
  root@你的VPS_IP:/opt/ytdl/
```

### 6. 設定環境變數

在 **VPS** 上執行：

```bash
cd /opt/ytdl

# 建立 .env 檔案
nano .env
```

填入以下內容（請替換成你的實際值）：

```env
# API 認證（請換成你自己的安全密碼）
API_TOKEN=你的長隨機密碼_至少32字元

# 儲存模式
STORAGE_MODE=r2

# Cloudflare R2
R2_ACCOUNT_ID=你的account_id
R2_ACCESS_KEY_ID=你的access_key_id
R2_SECRET_ACCESS_KEY=你的secret_access_key
R2_BUCKET_NAME=ytdl-videos

# 網域設定（Caddy 會自動申請 HTTPS 憑證）
DOMAIN=ytdl.yourdomain.com

# 其他設定
URL_EXPIRY_MINUTES=30
RATE_LIMIT_PER_MINUTE=10
MAX_CONCURRENT_JOBS=2
```

儲存並設定權限：

```bash
chmod 600 .env
```

### 7. 啟動服務

```bash
cd /opt/ytdl

# 建立並啟動所有容器
docker compose up -d

# 查看狀態
docker compose ps

# 查看日誌（Ctrl+C 退出）
docker compose logs -f
```

### 8. 驗證部署

```bash
# 測試健康檢查
curl https://ytdl.yourdomain.com/health

# 預期回應
# {"status":"ok","storage_mode":"r2"}
```

---

## 第三部分：測試完整流程

從你的電腦或手機測試：

```bash
# 1. 建立下載任務
curl -X POST https://ytdl.yourdomain.com/jobs \
  -H "X-API-Token: 你的API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720"}'

# 回應範例：
# {"job_id":"abc123...","status":"queued"}
```

```bash
# 2. 查詢狀態（用回傳的 job_id）
curl https://ytdl.yourdomain.com/jobs/abc123... \
  -H "X-API-Token: 你的API_TOKEN"

# 完成時回應：
# {"job_id":"...","status":"done","download_url":"https://...","filename":"..."}
```

```bash
# 3. 下載影片
curl -O "回傳的download_url"
```

---

## 費用概估

| 項目 | 費用 |
|------|------|
| Hetzner CPX11 | ~€4.85/月（約 $5.3 USD） |
| Cloudflare R2 儲存 | 10GB/月 免費，超過 $0.015/GB |
| Cloudflare R2 操作 | Class A: 100萬次/月免費，Class B: 1000萬次/月免費 |
| 網域 | 依你的網域商而定 |

**總計約 $5-6 USD/月**（個人使用量）

---

## 常用維護指令

### 查看服務狀態

```bash
cd /opt/ytdl

# 查看所有容器狀態
docker compose ps

# 查看即時日誌
docker compose logs -f

# 只看 worker 日誌
docker compose logs -f worker

# 只看 API 日誌
docker compose logs -f api
```

### 重啟服務

```bash
# 重啟所有服務
docker compose restart

# 只重啟 worker
docker compose restart worker
```

### 更新程式碼

在本機修改程式碼後：

```bash
# 1. 在本機上傳新檔案
rsync -avz --exclude '.venv' --exclude 'downloads' --exclude '__pycache__' \
  ./ root@你的VPS_IP:/opt/ytdl/

# 2. 在 VPS 上重新建構並啟動
ssh root@你的VPS_IP "cd /opt/ytdl && docker compose up -d --build"
```

### 查看磁碟使用

```bash
# 查看磁碟空間
df -h

# 查看 Docker 使用的空間
docker system df

# 清理未使用的 Docker 資源
docker system prune -f
```

### 查看 R2 儲存使用量

在 Cloudflare Dashboard → R2 → 你的 bucket → Metrics

---

## 疑難排解

### Caddy 無法取得 HTTPS 憑證

確認：
1. DNS A 記錄已正確指向 VPS IP
2. 防火牆允許 80 和 443 port
3. DOMAIN 環境變數設定正確

```bash
# 檢查防火牆
ufw status

# 開放 port（如果使用 ufw）
ufw allow 80
ufw allow 443
```

### Worker 無法連線到 R2

確認 `.env` 中的 R2 設定正確：
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`

```bash
# 查看 worker 錯誤日誌
docker compose logs worker | grep -i error
```

### 下載失敗

```bash
# 查看詳細 worker 日誌
docker compose logs -f worker

# 進入 worker 容器除錯
docker compose exec worker bash
```

### 重設所有服務

```bash
cd /opt/ytdl

# 停止並移除所有容器
docker compose down

# 重新建構並啟動
docker compose up -d --build
```

---

## 安全建議

1. **API Token**：使用長隨機字串（至少 32 字元）
   ```bash
   # 生成安全的 token
   openssl rand -hex 32
   ```

2. **定期更新**：
   ```bash
   apt update && apt upgrade -y
   docker compose pull
   docker compose up -d
   ```

3. **監控磁碟空間**：設定警報避免磁碟滿載

4. **備份 .env**：妥善保管環境變數檔案
