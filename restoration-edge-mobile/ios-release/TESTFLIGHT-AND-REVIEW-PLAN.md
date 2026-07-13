# TestFlight and App Review Plan

## Build sequence

1. `npm ci --legacy-peer-deps`
2. `npm run verify:release`
3. `npx expo prebuild --clean`
4. `eas build --profile development --platform ios`
5. Install on registered iPhone and verify startup, auth and local inference
6. `eas build --profile preview --platform ios`
7. Upload to internal TestFlight
8. Complete internal test matrix
9. `eas build --profile production --platform ios`
10. `eas submit --profile production --platform ios`

## Internal TestFlight matrix

### Devices

- Current-generation iPhone Pro / Pro Max
- Older supported iPhone with less memory
- iPad only if `supportsTablet` remains enabled

### Core flows

- Sign up
- Email verification
- Sign in / sign out
- Password reset
- Select photo from Photos
- Select media from Files
- On-device restoration
- Save result to Photos / Files
- Personal Worker pairing
- Long video task creation
- Pause / cancel / resume
- Cloud relay backpressure
- Result validation and download
- Account deletion

### Failure cases

- Offline at launch
- Network interruption during upload
- Worker unavailable
- Worker version mismatch
- Local disk insufficient
- Model download interrupted
- Model hash mismatch
- App backgrounded during task
- App killed and relaunched
- Low Power Mode
- High thermal state
- Storage quota exceeded
- Supabase session expired

### Privacy checks

- Original media stays local in on-device mode
- Direct Worker mode does not upload source to cloud storage
- Cloud relay chunks are private
- RLS prevents cross-account access
- Deleted account cannot access old jobs
- No advertising ID access
- No hidden analytics SDK

### Accessibility

- VoiceOver labels
- Dynamic Type
- Minimum tap targets
- Color contrast
- Progress not communicated by color alone
- Error messages include recovery action

## Exit criteria for production build

- No blocker or critical defect
- No crash in primary flows
- Account deletion verified end to end
- Privacy manifest matches final binary
- App Privacy form matches final binary
- Screenshot content matches shipping UI
- Reviewer account works
- Support and privacy URLs return HTTP 200
- Long-running tasks recover after interruption
- Personal Worker optional path is clearly labeled
- AI limitations and content-rights confirmation are visible

## App Review response template

If Apple asks why a local worker is used:

> The Personal Worker is an optional companion for long-running video processing. The app's core photo restoration flow runs directly on iPhone and can be fully reviewed without the companion. The worker is owned and operated by the user, communicates over the local device connection, and is not a mechanism for downloading executable code into the iOS app.

If Apple asks about generated detail:

> The app labels model-generated detail as enhancement or estimation and does not present it as verified original evidence. A conservative evidence mode avoids generative reconstruction.

If Apple asks about account deletion:

> The Account screen includes a direct deletion action. It removes product data, private media, worker tokens and the authentication account or completes the documented compliant deletion workflow without requiring the user to contact support.
