# Architecture and engineering decisions

## Request boundary

The webhook streams at most 1 MiB, verifies HMAC-SHA256 over the original bytes,
validates the event, and inserts a delivery/job inside a transaction. No inference
or GitHub API call delays the acknowledgement. A delivery ID maps to a job;
repository/PR/commit uniqueness also prevents duplicate jobs across redeliveries.

## Durable execution

SQLite WAL provides transactional claims on a shared local disk without another
service dependency. `BEGIN IMMEDIATE` serializes claims and publication jobs for
the same PR. Each claim receives an owner token and renewable lease. Database
updates are fenced by owner; expired jobs can be recovered by another worker.
Failures retain safe categories rather than upstream response bodies or tokens.

This favors a simple, demonstrable single-host application. A multi-host service
needs PostgreSQL/another durable queue, coordinated ownership and migrations.
Do not put this SQLite database on NFS or separate container volumes.

## Analysis boundary

GitHub App mode generates a short-lived RS256 JWT and obtains an installation
token per job. Policy is read from the PR's base SHA, not proposed code. Files
are paginated; missing/truncated patches and exhausted budgets become explicit
coverage gaps. Each complete eligible file patch is a bounded model request.

Model output must satisfy the typed finding schema and reference a valid old/new
diff location. Incomplete model responses fail closed. Category/severity filters
are applied only after validation. Actual usage and prompt/model identity are
retained with the result. An empty result never means unreviewed files passed.

## Publication boundary

Validated results are saved before GitHub writes. Retries reuse the result and
look up bot-owned markers to avoid reposting exact findings. Human comments are
never edited. One bot-owned summary is updated and opposite managed labels are
removed. The PR head is checked before publication steps; comments attach to the
reviewed commit. Cross-system races and ambiguous timeouts remain possible.

## Operator boundary

The dashboard HTML contains no repository data. Bearer-authenticated APIs expose
job history and aggregate usage; tokens remain in browser memory only. Dynamic
values use DOM text nodes, not HTML interpolation. CSP and no-store headers
reduce script injection and caching exposure. This is single-operator access,
not organization-level multi-tenant authorization.

## Evaluation boundary

Versioned fixtures keep expected labels separate from the model request. Reports
retain raw predictions and a dataset hash. Location/category scores are useful
regression signals but require semantic human adjudication before defect-quality
claims. Clean controls matter as much as seeded bugs: unnecessary comments can
make an otherwise capable reviewer unusable.
