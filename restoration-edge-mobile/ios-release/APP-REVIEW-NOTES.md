# App Review Notes Draft

## Review summary

Restoration Edge helps users improve photos and videos they own or are authorized to process. It can process photos on-device and send long-running jobs to the user's own Personal Worker.

The app does not claim to recover deleted or intentionally redacted pixels. Any AI-generated detail is labeled as an enhancement or estimate.

## Reviewer account

- Email: `REVIEW_ACCOUNT_EMAIL`
- Password: `REVIEW_ACCOUNT_PASSWORD`

Do not commit real credentials. Enter them only in App Store Connect Review Information.

## Primary review flow

1. Sign in with the reviewer account.
2. Choose a sample image from Photos or Files.
3. Select `On-device` processing.
4. Keep the default preset.
5. Accept the content-rights confirmation.
6. Start the task.
7. Open Jobs to view progress and the result.
8. Open Account to inspect privacy and account deletion controls.

## Personal Worker flow

The Personal Worker is optional and is not required to review the core on-device image flow.

If Apple requests the worker flow:

1. Install the provided Personal Worker on a macOS or Windows test machine.
2. Start the worker on `127.0.0.1:8787`.
3. Create a Worker Token in the app.
4. Pair the app using the local pairing secret.
5. Choose a video and select Personal Worker mode.

## Network services

- Supabase Auth, database, private storage and edge functions
- Public support and privacy pages on Vercel
- Optional model download endpoint
- Optional local Personal Worker on localhost

## Content rights and privacy

Users must confirm that they own or are authorized to process selected media. The app is not intended to defeat another person's privacy protection.

## Account deletion

The account screen contains an in-app account deletion action. The production build must delete product data, private media, worker tokens and the authentication account or complete a compliant deletion workflow.

## Export compliance

The app uses standard HTTPS/TLS and SHA-256 integrity checks. The production submission should answer the export-compliance questions based on the final binary and legal determination. The intended Info.plist value is `ITSAppUsesNonExemptEncryption=false` if the final binary uses no non-exempt encryption.

## AI disclosure

The app distinguishes:

- deterministic restoration and enhancement
- model-generated or estimated detail
- conservative evidence mode that avoids generative reconstruction

The app does not present generated details as verified original evidence.
