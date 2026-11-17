# Verification snapshot

Session date: November 18, 2026 (Asia/Kolkata). Assigned feature commit dates are
documented separately in BUILD_HISTORY.md.

| Check | Observed result |
| --- | --- |
| Automated tests | 41 passed |
| Application statement coverage | 86.28%; CI gate is 80% |
| Ruff lint and format | Passed |
| Python compilation | Passed |
| JavaScript syntax | Passed (`node --check`) |
| Dependency consistency | Passed (`pip check`) |
| Compose and workflow YAML | Parsed successfully |
| Recorded dataset hash | Matches the versioned report |
| Documentation file links | Verified |
| Dashboard browser verification | Sign-in, details, responsive layout, disconnect |
| Live Groq benchmark | 30/30 cases completed; see EVALUATION.md |
| Live GitHub personal-token authentication | HTTP 401; configured token not accepted |
| Live GitHub App installation | Not provisioned/verified |
| Docker image build | Not run locally; Docker is unavailable |
| Hosted GitHub Actions run | Test and container jobs passed on the published feature branch |
| Public deployment | Not provisioned |

The test client emits one Starlette/httpx deprecation warning; it did not affect
the successful tests. Tests and dashboard screenshots use isolated synthetic
data. No GitHub PR comments were posted during verification.

## To enable real reviews

Replace the invalid `GITHUB_TOKEN` in your local `.env` with a valid fine-grained
token, or configure/install the GitHub App following GITHUB_APP.md. Do not paste
credentials into chat or commit them. Confirm required repository permissions,
then run the live acceptance walkthrough in DEMO.md on your selected repository.

The container build is now verified by hosted CI. A public deployment still
requires your chosen HTTPS host and shared persistent storage for the API/worker.
Until live acceptance checks succeed, describe this as implemented and tested,
not a verified deployment.

## Pull request integration check

The published feature branch's [Verify workflow](https://github.com/dhananjay-wagh/ai-pr-reviewer/actions/runs/44163493152)
passed its test and container jobs, including an actual Docker image build and
API health smoke test. The PR's red merge status was caused by conflicts in
`README.md` and `app/utils.py`, rather than failed checks.

The integration keeps the expanded README with main's explicit `tests` directory.
Webhook signature helpers remain in `app/utils.py`; model configuration is now in
`app/model.py` and the `GROQ_MODEL` environment variable. Main's older hard-coded
`qwen/qwen3.6-27b` model was absent from the configured Groq account's model list
when checked on November 18, 2026. The available, previously benchmarked
`openai/gpt-oss-120b` remains the configurable default. No credentials were changed.
