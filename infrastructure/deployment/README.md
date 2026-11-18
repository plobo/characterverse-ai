# Deployment

| Environment | Database | Queue | Storage | Notes |
|---|---|---|---|---|
| local | SQLite or Compose Postgres | thread queue or Compose Redis/RQ | filesystem volume | mock AI adapters, dev auth on |
| staging | managed PostgreSQL (separate) | managed Redis | S3-compatible bucket (separate) | restricted test users, worker CPU/mem limits, provider budgets + alerts |
| production | managed PostgreSQL + PITR backups | managed Redis / durable queue | S3-compatible bucket + CDN | `CV_ENV=production` refuses to boot with dev secrets or dev auth |

Required production settings: `CV_JWT_SECRET`, `CV_SIGNING_SECRET` (from secret manager), `CV_ALLOW_DEV_AUTH=false`,
`CV_DATABASE_URL`, `CV_REDIS_URL`, `CV_QUEUE_BACKEND=rq`, `CV_DENYLIST_PATH` (trust & safety list), OIDC verifier config.

GPU workers are **not** provisioned until benchmarks show CPU rendering is insufficient (plan §17).
Restore drills: monthly restore of the latest PostgreSQL snapshot into staging; record the result in the ops log.
