# Operations

Run the API with `uvicorn app.main:app` and a separate worker with
`python -m app.worker`. Both processes must use the same `DATABASE_PATH`.
The webhook verifies the signature, persists the delivery, and responds 202.
No model or GitHub network work is performed inside the webhook request.

SQLite WAL is intentional for a single-host deployment. Use a local persistent
disk, not NFS or independently replicated container filesystems. Queue claims
are transactional; a PR is processed by one worker at a time. Crashed jobs are
reclaimed after their lease expires. Workers renew leases every 30 seconds;
jobs have a ten-minute deadline and at most three attempts for transient errors.

Repeated deliveries and commits return the existing job. Failed jobs are retained
for diagnosis, not silently treated as successful. Job status is available from
`GET /api/jobs/{id}` with `Authorization: Bearer <DASHBOARD_TOKEN>`.

Validated analysis is checkpointed before publishing. If GitHub writes fail,
retries reuse those exact findings instead of calling the model again and
generating different duplicate comments. Operators can retry a failed job with
`POST /api/jobs/{id}/retry` using the same bearer token, or the dashboard's retry
button. Manual retries are recorded in `retry_audit` and start a new three-attempt
cycle. Queued, running and completed jobs cannot be manually retried.

Publication is best-effort idempotent, not an exactly-once transaction across
SQLite and GitHub. A commit can change between the last check and a write, and a
network timeout can leave an ambiguous result. Commit-linked comments and marker
lookups reduce the impact; inspect GitHub when a publication remains failed.

Back up the database with SQLite's backup API (including WAL contents), rather
than copying only the live `.db` file. Restrict disk access: findings may contain
private code. For multi-host deployment, replace the store with a transactional
PostgreSQL queue before scaling replicas.
