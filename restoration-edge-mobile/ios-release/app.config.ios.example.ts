import type { ExpoConfig } from "expo/config";

const config: ExpoConfig = {
  name: "Restoration Edge",
  slug: "restoration-edge-mobile",
  version: "0.2.0",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  ios: {
    supportsTablet: true,
    bundleIdentifier: "com.paq.restorationedge",
    buildNumber: "1",
    infoPlist: {
      ITSAppUsesNonExemptEncryption: false,
      NSPhotoLibraryUsageDescription:
        "允許你從照片圖庫選取要修復的照片與影片。",
      NSPhotoLibraryAddUsageDescription:
        "允許你把修復後的照片與影片儲存回照片圖庫。",
      NSCameraUsageDescription:
        "允許你拍攝要修復的照片或影片。",
      NSAppTransportSecurity: {
        NSAllowsLocalNetworking: true,
      },
    },
    privacyManifests: {
      NSPrivacyTracking: false,
      NSPrivacyTrackingDomains: [],
      NSPrivacyCollectedDataTypes: [],
      NSPrivacyAccessedAPITypes: [],
    },
  },
  extra: {
    eas: {
      projectId: "EAS_PROJECT_ID",
    },
  },
};

export default config;

// 注意：
// 1. 若實際使用 LAN Worker 探索，再加入 NSLocalNetworkUsageDescription 與 Bonjour services。
// 2. 若不使用相機，刪除 NSCameraUsageDescription。
// 3. privacyManifests 必須依實際依賴與 Xcode Privacy Report 更新，不能直接照抄空陣列送審。
