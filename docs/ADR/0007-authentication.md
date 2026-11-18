# ADR 0007 — Authentication

- **Status:** Accepted · **Date:** 2026-11-17

`POST /v1/auth/session` exchanges an identity token for a short-lived access token (HS256 JWT, 1 h) plus a
90-day refresh token; `POST /v1/auth/refresh` renews the session. Clients refresh transparently on `AUTH_INVALID`
(iOS `APIClient`, Android OkHttp `RefreshAuthenticator`) and only sign out when refresh fails. Providers:
`oidc` (production; verifier injected per deployment — any OIDC-compatible provider or Firebase Auth after cost/terms
review), `dev` (local/test only; refused when `CV_ENV=production` or `CV_ALLOW_DEV_AUTH=false`) and `guest`
(anonymous account for local drafts). Tokens are stored in the iOS Keychain (actor-isolated) and Android Keystore
(AES-GCM key, ciphertext in DataStore). Production boot fails if dev secrets or dev auth are configured.
Refresh-token rotation/revocation and the OIDC verifier implementation are open items in `docs/IMPLEMENTATION_STATUS.md`.
