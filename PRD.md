# PRD：iPhone 捷徑一鍵下載影片到相簿（Option A MVP）

## 1. 背景與問題定義

使用者希望在 Apple iPhone 上「輸入/分享一個 YouTube 連結 + 選擇品質」，即可由雲端完成下載與封裝後，透過 Apple Shortcuts **直接存入相簿**，達到接近「deploy and forget」的自用體驗。

iOS Safari/網頁環境無法直接寫入相簿（權限與 sandbox 限制），因此 MVP 以捷徑完成最後一步「寫入相簿」。

---

## 2. 目標與成功指標

### 2.1 目標（Goals）

1. 使用者可透過捷徑：

   * 貼上/分享影片 URL
   * 選擇品質（例如 1080/720/480）
   * 觸發雲端下載任務、等待完成
   * 自動下載成品 mp4 並存入 iPhone 相簿
2. 雲端端採用：

   * 算力：Hetzner VPS
   * 物件儲存：Cloudflare R2（成品與交付）
   * 入口與 TLS：Caddy（自動 HTTPS、反向代理）
3. 可靠性：

   * 任務執行失敗可回傳可讀錯誤
   * 成品連結短效、可下載成功率高
4. 運維低摩擦（deploy and forget）：

   * 檔案自動清理（lifecycle）
   * TLS 自動續期（Let's Encrypt）
   * 容器可重啟自愈

### 2.2 非目標（Non-Goals）

* 不做 web 前端 UI（MVP 只做捷徑入口）
* 不做使用者系統、多租戶、付費
* 不做音訊抽取流程（音訊需求留作後續擴充）
* 不承諾下載速度提升（效能主要受網路與來源限制）

### 2.3 成功指標（Success Metrics）

* ≥90% 的任務在 1 次嘗試內成功產生可下載 mp4（以自用實測為準）
* 捷徑「下載→存相簿」成功率 ≥90%
* VPS 磁碟使用量長期穩定（不累積成品檔）
* TLS 憑證不需人工介入（6 個月內零事故）

---

## 3. 目標使用者與使用情境

### Persona：自用開發者

* 想在手機端快速保存影片到相簿
* 不想在手機上跑命令列工具
* 希望雲端常駐、少維護

### 典型情境

1. 在 YouTube App/Safari 看到影片 → 分享 → 捷徑 → 選 720p → 等待 → 相簿出現影片
2. 直接在捷徑貼上 URL → 選 1080p → 保存

---

## 4. 端到端流程

### 4.1 主流程（Happy Path）

1. 使用者觸發捷徑（分享表單或手動貼 URL）
2. 捷徑呼叫 API：`POST /jobs`（帶 url、quality）
3. API 建立 job → 回 `job_id`
4. 捷徑輪詢：`GET /jobs/{job_id}` 直到 `status=done`
5. API 回 `download_url`（指向 R2 的短效 URL）
6. 捷徑以該 URL 下載 mp4 → 存入相簿

### 4.2 失敗流程（Error Paths）

* URL 不合法 / 不支援：`status=error` + `error_code=INVALID_URL`
* 來源暫時不可用：`error_code=UPSTREAM_FAILURE`
* 下載/合併失敗：`error_code=DOWNLOAD_FAILED | MERGE_FAILED`
* 上傳 R2 失敗：`error_code=UPLOAD_FAILED`
* 捷徑下載失敗（網路/過期）：提示使用者重試（可自動重新抓一次 job 狀態）

---

## 5. 系統架構與技術方案

### 5.1 高層架構

* VPS（Hetzner）

  * `caddy`：TLS + Reverse proxy
  * `api`：REST API（job 建立/查詢）
  * `worker`：背景任務（下載/合併/上傳）
  * `queue`：輕量任務佇列（可用 Redis）
* R2

  * 存放成品 mp4
  * lifecycle 自動刪除（例如 3 天/7 天）
  * 提供短效下載 URL（signed URL）

### 5.2 下載與封裝策略（效能與相容性）

* 下載引擎：yt-dlp
* 外部 downloader：aria2（提高並行分段、重試能力）
* 合併/封裝：FFmpeg
* 原則：

  * **避免 re-encode**（只 merge/remux），降低 CPU 與時間成本
  * 僅在必要時 remux 成 mp4，讓 iOS 播放與相簿相容性更高

---

## 6. API 規格（MVP）

### 6.1 Authentication

* Header：`X-API-Token: <token>`
* Caddy 亦可加 Basic Auth 作第二道（可選）

### 6.2 `POST /jobs`

**Request**

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "quality": "1080"
}
```

**Response (200)**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

**Response (4xx)**

```json
{
  "error_code": "INVALID_URL",
  "message": "..."
}
```

### 6.3 `GET /jobs/{job_id}`

**Response**

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

**Done**

```json
{
  "job_id": "uuid",
  "status": "done",
  "download_url": "https://...signed...",
  "expires_at": "2026-02-01T12:34:56Z",
  "filename": "....mp4"
}
```

**Error**

```json
{
  "job_id": "uuid",
  "status": "error",
  "error_code": "MERGE_FAILED",
  "message": "..."
}
```

---

## 7. iPhone 捷徑規格（MVP）

### 7.1 觸發方式

* 分享表單：接受 URL
* 手動執行：要求輸入 URL

### 7.2 動作流程（概念）

1. 取得 URL
2. 選擇品質（清單）
3. 呼叫 `POST /jobs`
4. Repeat：

   * Wait 2s
   * GET `/jobs/{id}`
   * 若 done → break
   * 若 error → 顯示錯誤並結束
5. Get Contents of URL（download_url）
6. Save to Photo Album（存入相簿）

### 7.3 UX 要求

* 顯示目前狀態（queued/running）
* 超時策略：例如最多輪詢 10 分鐘，超時提示「稍後再查」

---

## 8. 安全、風控與合規（自用最小集合）

### 8.1 基本安全

* API token 必須是長隨機字串
* Rate limit（至少每分鐘 job 次數限制）
* 輸入白名單：

  * quality 僅允許固定枚舉
  * URL 僅允許 youtube domain（MVP 可先硬限制）
* 下載檔案命名與路徑嚴格控制（避免 path traversal）

### 8.2 檔案與連結

* download_url 採短效（建議 15–30 分鐘）
* R2 lifecycle 自動刪檔（降低長期留存風險）

---

## 9. 可觀測性與維運（deploy and forget 核心）

### 9.1 Logging

* job lifecycle：created → running → done/error
* 下載/合併/上傳各階段耗時（便於定位慢點）
* 失敗時保留最後 N 行 stderr（避免噪音太大）

### 9.2 Monitoring（MVP 最小）

* 容器 healthcheck
* VPS 磁碟剩餘空間（暫存用）
* 失敗率告警（可先用簡單 webhook/Email，後續再接監控）

### 9.3 自動清理

* VPS：只保留短暫暫存檔（worker 成功上傳後立即刪）
* R2：lifecycle 自動刪除 N 天前物件

---

## 10. 容量與限制（MVP）

* 同時執行 job：預設 1–2（避免 VPS 被打爆）
* 單檔大小：由 R2 物件限制與 VPS 磁碟暫存決定（MVP 可先不硬限制，但要防爆）
* 並行分段：`concurrent-fragments` 8（可調）

---

## 11. 里程碑

### Milestone 0：可用性打通（1 次）

* API 可建 job、查狀態
* worker 可產生 mp4 並上傳 R2
* 捷徑可存相簿成功

### Milestone 1：穩定化

* 強化錯誤碼與訊息
* 加入 rate limit、URL 白名單
* R2 lifecycle 上線
* Caddy TLS、反向代理與基礎安全頭

### Milestone 2：體驗提升（可選）

* job 進度更準（下載百分比）
* 失敗重試策略（例如 download 失敗重試 1 次）
* 後台簡單狀態頁（非必要）

---

## 12. 風險與對策

1. **來源端變動導致下載失效**

   * 對策：可控更新節奏（手動或週期更新），保留快速更新路徑
2. **捷徑下載大檔不穩**

   * 對策：download_url 直連物件、TTL 足夠長、避免需 cookie
3. **VPS 暫存磁碟爆掉**

   * 對策：限制並行 job、上傳後立刪、暫存目錄監控
4. **token 洩漏**

   * 對策：可輪換 token；Caddy 端加 Basic Auth；限制來源 IP（可選）

---

## 13. 後續擴充（不影響 MVP）

* 音訊抽取（m4a/opus）→ 存檔案而非相簿
* Web 一頁式 UI（貼 URL/選品質/完成後一鍵喚起捷徑）
* 多裝置支援（Android/桌面）

---

如果你要我把這份 PRD 直接「落地成可部署的最小實作規格」，我下一步會補上：

* 具體 docker-compose 服務清單與環境變數（R2 keys、API token、domain）
* Caddy 路由規格
* API request/response schema（含 error_code 列表）
* 捷徑步驟清單（逐步對應到 actions）
