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
| Hosted GitHub Actions run | Not run; commits remain local |
| Public deployment | Not provisioned |

The test client emits one Starlette/httpx deprecation warning; it did not affect
the successful tests. Tests and dashboard screenshots use isolated synthetic
data. No GitHub PR comments were posted during verification.

## To enable real reviews

Replace the invalid `GITHUB_TOKEN` in your local `.env` with a valid fine-grained
token, or configure/install the GitHub App following GITHUB_APP.md. Do not paste
credentials into chat or commit them. Confirm required repository permissions,
then run the live acceptance walkthrough in DEMO.md on your selected repository.

Build/run the Docker image on a Docker-enabled host or push the branch to run
its container CI job. A public deployment requires your chosen HTTPS host and
shared persistent storage for the API/worker. Until those checks succeed,
describe this as implemented and locally verified, not a verified deployment.
