# Restoration Edge Mobile — Apple App Store Roadmap

目標：把目前的 iOS Release Candidate 推進到 TestFlight、App Store Review 與正式上架。

## Phase 0 — 帳號與法律前置

- [ ] 加入 Apple Developer Program
- [ ] 確認開發者名稱：個人或公司法人
- [ ] 建立 App Store Connect App
- [ ] 確認 App 名稱與副標題可用
- [ ] 建立唯一 Bundle ID
- [ ] 建立 App Store Connect 使用者與角色
- [ ] 完成 Agreements、Tax、Banking（若有付費、訂閱或 App 內購）
- [ ] 準備客服信箱、隱私政策 URL、支援 URL

## Phase 1 — iOS 身分與簽章

- [ ] Bundle ID：建議 `com.paq.restorationedge`
- [ ] Apple Team ID
- [ ] Distribution Certificate
- [ ] App Store Provisioning Profile
- [ ] Push / Associated Domains / Sign in with Apple 能力只在實際使用時開啟
- [ ] EAS Credentials 與 App Store Connect API Key

## Phase 2 — 專案 iOS 設定

- [ ] App 顯示名稱、版本、Build Number
- [ ] 1024×1024 App Icon，不含透明
- [ ] iPhone / iPad 支援範圍
- [ ] 最低 iOS 版本
- [ ] `ITSAppUsesNonExemptEncryption=false`（僅在確認不使用非豁免加密後）
- [ ] Photo Picker / Files Picker / Camera 權限文字
- [ ] Localhost / 本地 Worker 的 ATS 設定
- [ ] 若使用 LAN Worker 探索，再加入 Local Network 權限與 Bonjour services
- [ ] 背景處理能力只在確實需要時宣告
- [ ] Privacy Manifest（`PrivacyInfo.xcprivacy`）
- [ ] 第三方 SDK Privacy Manifest 檢查

## Phase 3 — App Store 合規

- [ ] App 內可直接刪除帳號
- [ ] 隱私政策與 App 實際資料流一致
- [ ] App Privacy 表單完成
- [ ] 不出售媒體、不用媒體訓練模型的聲明可被驗證
- [ ] 不宣稱找回已刪除、塗黑、強馬賽克遮蔽的真實像素
- [ ] 使用者素材授權確認
- [ ] 未加入第三方登入前，不需要 Sign in with Apple
- [ ] 若加入 Google / Facebook 登入，必須同步加入 Sign in with Apple
- [ ] 若加入追蹤或跨 App 廣告識別，必須評估 ATT；目前預設不使用追蹤
- [ ] AI 功能說明清楚標示生成／推測內容
- [ ] 內容安全與濫用回報流程

## Phase 4 — 品質與穩定性

- [ ] 真機測試：至少一台新 iPhone、一台較舊 iPhone
- [ ] 記憶體壓力、低耗電、過熱、離線、弱網測試
- [ ] 大圖、長影片、取消、恢復、重試
- [ ] Personal Worker 配對、失聯、版本不相容、磁碟不足
- [ ] 帳號註冊、登入、登出、重設密碼、刪除帳號
- [ ] App 從背景恢復與冷啟動
- [ ] Crash-free 與 ANR 類問題觀察
- [ ] VoiceOver、Dynamic Type、對比與觸控尺寸

## Phase 5 — TestFlight

- [ ] 建立 Development Build
- [ ] 建立 Internal TestFlight Build
- [ ] 填寫 Beta App Description
- [ ] 提供測試帳號或審核模式
- [ ] 完成 Export Compliance
- [ ] 內部測試 3–7 天
- [ ] 外部測試群組與測試說明
- [ ] 收集 Crash、啟動失敗、網路錯誤、處理失敗率

## Phase 6 — App Store 素材

- [ ] App 名稱
- [ ] 副標題
- [ ] 關鍵字
- [ ] 描述
- [ ] Promotional Text
- [ ] Support URL
- [ ] Privacy Policy URL
- [ ] Marketing URL（可選）
- [ ] iPhone 6.9 吋與 6.5 吋截圖
- [ ] iPad 截圖（若支援 iPad）
- [ ] App Preview 影片（可選）
- [ ] App Icon
- [ ] 年齡分級問卷
- [ ] App Review Notes
- [ ] Reviewer 帳號與操作步驟

## Phase 7 — 送審與上線

- [ ] 選擇正式 Build
- [ ] 完成 App Privacy
- [ ] 完成 Export Compliance
- [ ] 完成 Content Rights
- [ ] 完成 Advertising Identifier 問卷
- [ ] 設定自動或手動發布
- [ ] 送審
- [ ] 回應審核問題
- [ ] 上線後 24–72 小時監測

## Phase 8 — 上線後維護

- [ ] Crash 與啟動失敗監測
- [ ] API / Worker 版本相容矩陣
- [ ] 模型與依賴漏洞更新
- [ ] 隱私政策與資料流變更同步
- [ ] App Store 評論與客服回覆
- [ ] 每次版本更新重跑 Release Gate
- [ ] 每季檢查 App Review Guidelines 變更

## 目前已完成

- React Native / Expo 專案基線
- iOS 原生預建
- ONNX 實際推論
- Personal Worker 混合運算
- Supabase Auth / RLS / 私有資料
- 長影片分段與中斷恢復
- 正式依賴漏洞為 0
- 兩小時影片壓力測試

## 目前外部阻塞

- Apple Developer Program 帳號
- Team ID
- App Store Connect App
- App Store Connect API Key
- 正式 Bundle ID 最終確認
- 正式 App Icon 與商店截圖
- TestFlight 真機測試
