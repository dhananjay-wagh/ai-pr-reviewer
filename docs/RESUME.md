# Resume and interview material

## Project title

**AI Code Reviewer — GitHub App with durable review processing**

## Resume bullets (implemented behavior)

- Built a FastAPI/Groq code-review service with signed GitHub webhooks, GitHub App
  installation authentication, diff-validated inline findings and review summaries.
- Engineered a persistent worker queue with duplicate-delivery protection,
  renewable leases, crash recovery, checkpointed publication and audited retries.
- Developed an authenticated review dashboard and a 30-case Python/JavaScript
  evaluation harness tracking review scope, latency, token usage and model errors;
  added Docker deployment and automated lint, tests and coverage gates.

The implementation-session verification recorded 41 passing tests and 86.28%
application coverage. Treat this as a dated snapshot and rerun before reuse.

Use two or three bullets depending on available space. Link the repository and,
after deployment, a working demo. Do not list a public deployment or active app
installation until you have actually configured and verified it.

## Evidence to discuss

The recorded synthetic benchmark completed 30/30 cases with zero invalid finding
locations. Its 55.2% location/category precision and 80.0% recall are proxies;
do not rewrite them as production defect accuracy. Explain false positives and
how independently labeled real PRs and human adjudication would improve the
evaluation. Quote the current test count and coverage only from a fresh run.

## Interview walkthrough

1. **Problem:** PR reviewers need feedback that is relevant, correctly located,
   and clear about what was actually checked.
2. **Failure you solved:** malformed model output and truncated diffs used to look
   like approval; validation and explicit coverage prevent that conclusion.
3. **System design:** acknowledge webhooks quickly, then use transactional jobs
   and leases to do expensive work outside the request.
4. **Retry reasoning:** a failed write must reuse prior analysis, because model
   regeneration can produce different duplicate comments.
5. **Security choices:** installation tokens, HMAC, trusted base-commit policy,
   bounded inputs, no execution of PR code, single-operator dashboard auth.
6. **Tradeoffs:** SQLite simplifies one-host deployment; PostgreSQL is the next
   step for multiple hosts. External publication remains best-effort idempotent.
7. **Evaluation:** show raw predictions, clean controls, metric limitations and a
   concrete false positive instead of claiming the reviewer is always right.

## Next portfolio milestone

Deploy behind HTTPS, install the app on a demo repository, and review three
real PRs: one seeded bug, one clean change and one intentionally partial review.
Add screenshots/links to those PRs and manually adjudicate the findings. This is
the remaining external evidence needed before describing it as a deployed tool.
