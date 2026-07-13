# Privacy Data Map — App Store Connect

此文件用於填寫 App Store Connect 的 App Privacy 問卷。送審前必須再次依實際程式碼與 SDK 驗證。

## 預計收集的資料

### 聯絡資訊

- 電子郵件地址
- 用途：帳號驗證、登入、重設密碼、服務通知
- 是否與使用者身分連結：是
- 是否用於追蹤：否

### 使用者內容

- 使用者選取的照片與影片
- 工作檔名、檔案大小、媒體類型
- 修復設定、處理進度、錯誤與成品 metadata
- 用途：提供核心修復功能、工作恢復、成品下載
- 是否與使用者身分連結：工作 metadata 是；原始媒體依所選模式而定
- 是否用於追蹤：否

### 識別資訊

- 內部 User ID
- App 安裝／裝置識別碼（僅限產品裝置能力紀錄，不使用廣告 ID）
- 用途：帳號隔離、裝置能力同步、任務恢復
- 是否與使用者身分連結：是
- 是否用於追蹤：否

### 診斷資料

- 裝置型號、OS、記憶體、處理器數量、低耗電狀態、溫度級別
- 模型版本、執行 Provider、推論延遲與錯誤
- 用途：自動選擇安全運算路徑、穩定性與效能改善
- 是否與使用者身分連結：登入後可能連結
- 是否用於追蹤：否

## 預計不收集

- 精確位置
- 粗略位置
- 聯絡人
- 通訊錄
- 健康與健身
- 金融資訊
- 瀏覽歷史
- 搜尋歷史
- 廣告識別碼
- 跨 App 或跨網站追蹤資料

## 處理路徑

### Browser / Mobile local

原始照片留在裝置記憶體。只在使用者選擇保存時，將成品與工作 metadata 上傳至私人儲存。

### Direct Personal Worker

原始檔由裝置直接傳送至使用者自己的 Worker。雲端只保存任務狀態與必要 metadata。

### Cloud relay

來源拆成私有分段。Worker 驗證落盤後刪除雲端中繼片段。必須有保留期限與清理機制。

## 第三方處理者

- Apple：App Store、TestFlight、裝置服務
- Supabase：Auth、Postgres、Realtime、私人 Storage、Edge Functions
- Expo / EAS：建置與更新服務（依正式發行設定）
- Vercel：公開網站、支援頁與隱私政策

## App Tracking Transparency

目前產品不進行跨 App / 跨網站追蹤，也不使用 IDFA，因此不應顯示 ATT 權限提示。

若未來加入廣告、歸因或跨產品追蹤 SDK，必須重新評估並更新此文件與 App Privacy 表單。

## Account Deletion

若 App 允許建立帳號，必須在 App 內提供可找到、可完成的刪除帳號流程。送審版本不得只提供客服信箱。

最低驗收：

1. 刪除產品資料與私有媒體。
2. 撤銷 Worker Tokens。
3. 刪除或排程刪除 Auth 使用者。
4. 登出所有裝置。
5. 在 UI 顯示刪除結果與不可逆說明。

## Privacy Manifest

必須檢查：

- App 自身的 Required Reason APIs
- Expo / React Native / SQLite / FileSystem / SecureStore
- ONNX Runtime
- 其他原生 SDK

送審前使用 Xcode 的 Privacy Report 檢查是否有缺少原因碼或第三方 manifest。
