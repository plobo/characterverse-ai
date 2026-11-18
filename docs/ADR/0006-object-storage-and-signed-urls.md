# ADR 0006 — Object storage and signed URLs

- **Status:** Accepted · **Date:** 2026-11-17

Storage sits behind an S3-like interface (`put`, `exists`, `delete`, `signed_url`, `verify`). The local adapter
stores files on disk and issues **HMAC-SHA256 signed, expiring URLs** (`/v1/media/{key}?exp&sig` for GET,
`/v1/upload/{key}` for PUT). Path traversal is rejected; method is part of the signature; default TTL 15 minutes.
Uploads use presigned PUTs with declared MIME type and size, rights confirmation, magic-byte sniffing and one-shot
slots. Production uses an S3-compatible bucket with native presigned URLs (adapter to implement against the same
interface) and a CDN for approved static assets. Clients never receive storage credentials.
