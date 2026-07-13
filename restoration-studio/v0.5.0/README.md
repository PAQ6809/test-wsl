# Restoration Studio Cloud v0.5.0

Production: https://restoration-studio-cloud.vercel.app

This directory is the immutable, auditable source release for the Restoration Studio Cloud frontend and Personal Worker.

## Components

- `src/`: readable frontend source chunks loaded by the production bootstrap
- `loader.js`: immutable release loader pinned to a source commit
- `worker/`: complete Personal Worker source, installers, dependency pins and FFmpeg/OpenCV pipeline
- `source-manifest.json`: ordered source assembly manifest

## Processing routes

1. Browser image restoration: source stays in the browser; the restored result may be stored in the user's private Supabase bucket.
2. Direct local worker: large media is resumably transferred to `127.0.0.1:8787` and processed locally.
3. Cloud relay: 6 MB private chunks are consumed by the user's worker and deleted after fsynced, hash-verified local persistence.

## Trust policy

The system improves compression artifacts, noise, interlacing, banding and display resolution. It does not claim to recover pixels that were fully deleted, blacked out or intentionally redacted, and must not be used to defeat another person's privacy protection.

## Security

- Supabase Auth and Row Level Security
- Private object storage paths scoped by `auth.uid()`
- Revocable worker tokens stored only as SHA-256 hashes
- Worker bound to loopback only with a separate browser pairing secret
- Atomic checkpoints, SHA-256 verification and final duration/resolution validation

License for the Personal Worker source is MIT. Platform-specific services remain subject to their own terms.