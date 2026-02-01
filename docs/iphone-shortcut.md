# iPhone 捷徑設置教學 / iPhone Shortcut Setup Guide

本文件說明如何建立 iPhone 捷徑來下載 YouTube 影片到相簿。

This guide explains how to create an iPhone Shortcut to download YouTube videos to your photo album.

---

## 前置準備 / Prerequisites

1. 確認後端 API 已部署並可存取
2. 準備好你的 API Token
3. 準備好你的 API 網址（例如：`https://your-domain.com`）

---

## 建立捷徑 / Create Shortcut

打開 iPhone 的「捷徑」App，點選右上角 `+` 建立新捷徑。

### 步驟 1：設定捷徑接收分享 / Step 1: Configure Share Sheet

1. 點選捷徑名稱旁的 `ⓘ` 圖示
2. 啟用「在分享表單中顯示」
3. 接受類型選擇「URL」

### 步驟 2：取得 URL / Step 2: Get URL

新增動作：**如果**

```
如果「捷徑輸入」有任何值
```

**在「如果」區塊內**新增：
- 動作：**設定變數**
- 變數名稱：`VideoURL`
- 輸入：`捷徑輸入`

**在「否則」區塊內**新增：
- 動作：**要求輸入**
- 提示：`請輸入 YouTube 網址`
- 動作：**設定變數**
- 變數名稱：`VideoURL`
- 輸入：`要求輸入的結果`

### 步驟 3：選擇品質 / Step 3: Choose Quality

新增動作：**從選單中選擇**

- 提示：`選擇影片品質`
- 選項：
  - `720p`
  - `1080p`
  - `480p`
  - `最佳品質`

新增動作：**如果**

依選項設定變數 `Quality`：
- 720p → `720`
- 1080p → `1080`
- 480p → `480`
- 最佳品質 → `best`

### 步驟 4：建立下載任務 / Step 4: Create Job

新增動作：**取得 URL 的內容**

- URL：`https://your-domain.com/jobs`
- 方法：`POST`
- Headers：
  - `X-API-Token`: `你的API Token`
  - `Content-Type`: `application/json`
- 要求內文：JSON
  ```json
  {
    "url": [VideoURL變數],
    "quality": [Quality變數]
  }
  ```

新增動作：**從輸入取得字典值**
- 鍵：`job_id`
- 儲存到變數：`JobID`

### 步驟 5：輪詢等待完成 / Step 5: Poll Until Done

新增動作：**重複**

- 重複次數：`300`（最多等待 10 分鐘，每 2 秒檢查一次）

**在重複區塊內**：

1. 新增動作：**等待**
   - 秒數：`2`

2. 新增動作：**取得 URL 的內容**
   - URL：`https://your-domain.com/jobs/[JobID變數]`
   - 方法：`GET`
   - Headers：
     - `X-API-Token`: `你的API Token`

3. 新增動作：**從輸入取得字典值**
   - 鍵：`status`

4. 新增動作：**如果**
   - 條件：`status` 是 `done`
   - **在「如果」區塊內**：
     - 動作：**從輸入取得字典值**（對前一個 URL 的結果）
     - 鍵：`download_url`
     - 儲存到變數：`DownloadURL`
     - 動作：**退出捷徑的重複**

5. 新增另一個動作：**如果**
   - 條件：`status` 是 `error`
   - **在「如果」區塊內**：
     - 動作：**顯示提示**
     - 標題：`下載失敗`
     - 訊息：從字典取得 `message` 欄位
     - 動作：**停止捷徑**

### 步驟 6：下載並存入相簿 / Step 6: Download and Save

新增動作：**如果**

- 條件：`DownloadURL` 有任何值

**在「如果」區塊內**：

1. 新增動作：**取得 URL 的內容**
   - URL：`[DownloadURL變數]`

2. 新增動作：**儲存到相簿**
   - 輸入：上一步的結果

3. 新增動作：**顯示提示**
   - 標題：`完成`
   - 訊息：`影片已儲存到相簿`

**在「否則」區塊內**：

新增動作：**顯示提示**
- 標題：`超時`
- 訊息：`下載時間過長，請稍後再試`

---

## 完整捷徑流程圖 / Complete Flow

```
開始
  ↓
有分享輸入？ → 是 → 使用分享的 URL
  ↓ 否
要求輸入 URL
  ↓
選擇品質（720p/1080p/480p/best）
  ↓
POST /jobs → 取得 job_id
  ↓
重複（最多 300 次）：
  ├── 等待 2 秒
  ├── GET /jobs/{job_id}
  ├── status = done? → 取得 download_url → 跳出重複
  └── status = error? → 顯示錯誤 → 停止
  ↓
有 download_url？
  ├── 是 → 下載 → 存入相簿 → 完成
  └── 否 → 顯示超時訊息
```

---

## 使用方式 / How to Use

### 方式一：分享選單

1. 在 YouTube App 或 Safari 開啟影片
2. 點選分享按鈕
3. 選擇你建立的捷徑
4. 選擇品質
5. 等待下載完成

### 方式二：手動執行

1. 打開捷徑 App
2. 執行捷徑
3. 貼上 YouTube 網址
4. 選擇品質
5. 等待下載完成

---

## 疑難排解 / Troubleshooting

### 捷徑顯示「未授權」

- 確認 `X-API-Token` header 設定正確
- 確認 API Token 與後端設定一致

### 下載超時

- 長影片可能需要更多時間
- 可增加重複次數或等待時間
- 確認伺服器網路正常

### 影片無法播放

- 確認影片已完整下載
- 嘗試選擇較低品質重新下載

### 下載失敗

- 確認 YouTube 網址正確
- 部分影片可能有地區限制或私人設定
- 檢查伺服器日誌了解詳細錯誤
