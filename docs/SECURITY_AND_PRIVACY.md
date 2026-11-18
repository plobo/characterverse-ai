# Security and Privacy

| Control (plan §15) | Implementation |
|---|---|
| TLS everywhere | Android `network_security_config` blocks cleartext except the local dev host; iOS ATS allows only local networking |
| No secrets in mobile binaries | Clients hold only a short-lived session; storage uses signed URLs; production boot refuses dev secrets / dev auth |
| Short-lived signed media URLs | HMAC-SHA256, method-bound, 15 min default, expiry + tamper tests |
| Server-side ownership | `get_owned()` on every object route → 404 for non-owners; tested |
| Upload validation | declared MIME allow-list, size cap, rights confirmation, magic-byte sniff, one-shot slots, moderation of file name |
| Worker isolation | render workers run as uid 10001, CPU/memory limits in Compose; FFmpeg/Blender run as subprocesses with timeouts; scene documents are data only — no user scripts, shaders or code |
| Rate limits & quotas | per-user generation rate limit; max active renders per user; bounded retries |
| Moderation & audit | deny list (fuzzy/leet/accents/glued tokens) + imitation classifier; every decision stored in `moderation_events`; actions in `audit_events`; report/takedown endpoint |
| Data export / deletion | `GET /v1/me/export`; `DELETE /v1/me` hard-deletes characters, projects, renders, uploads and stored media, tombstones the user, retains content-free moderation/audit records |
| Credentials on device | iOS Keychain (`AfterFirstUnlockThisDeviceOnly`, actor-isolated); Android Keystore AES-GCM; Android backups exclude app data |
| Analytics consent | off by default; events never include prompts, dialogue, names or media |

## Retention (proposed — requires legal review)
Temporary render work dirs: 24 h. Uploads: 30 days unless attached to a project. Deleted accounts: content removed
immediately, tombstone + audit/moderation metadata 12 months. Logs: 30 days.

## Open items before launch
Legal review of terms, privacy notice (PIPEDA + provincial requirements), ownership language; OIDC verifier +
refresh tokens; Redis-backed rate limiter; malware scanning of uploads; encryption at rest settings on managed
PostgreSQL/S3; FFmpeg GPL review (see licences doc); penetration test.
