# GitHub App setup

1. Register an app under GitHub Settings → Developer settings → GitHub Apps.
2. Set its webhook URL to `https://YOUR_HOST/webhook` and create a webhook secret.
3. Subscribe to **Pull request** events. Set repository permissions:
   **Contents: read**, **Pull requests: read/write**, **Issues: read/write**
   (for labels and summary comments). Metadata is implicit.
4. Generate a private key and mount it outside the repository. Set
   `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_WEBHOOK_SECRET`,
   `GROQ_API_KEY`, and `DASHBOARD_TOKEN` in both API/worker environments.
5. Install the app on selected repositories. Optionally restrict them further
   with comma-separated `ALLOWED_REPOSITORIES=owner/repo,owner/other`.
6. Open a small test PR and inspect its webhook delivery and persisted job.

App mode signs an RS256 JWT, exchanges it for an installation token per job,
and uses the app's bot identity for comment ownership. It never falls back to
a personal token when app configuration or installation data is missing.
The worker does not persist tokens or private keys.

For a single-repository local demo, omit app variables and use a fine-grained
`GITHUB_TOKEN` with equivalent permissions. Set `ALLOWED_REPOSITORIES` to that
repository. Never commit `.env` or private keys.

References: [JWT authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app),
[installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
