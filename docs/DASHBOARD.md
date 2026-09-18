# Review desk

Open `/dashboard` on your running API and enter `DASHBOARD_TOKEN`. The token is
kept in page memory only, never URL parameters, local storage or cookies.
Disconnect clears the token and rendered job data. Deploy behind HTTPS.

The dashboard shows the latest 50 jobs, status, findings, coverage, ignored and
skipped files, error categories, token usage and duration. Metrics explicitly
identify their sample window (latest 100 completed jobs). Use Refresh for new
activity. All job APIs require the bearer token, even when the HTML is public.
This is a single-operator dashboard, not a multi-tenant access-control system.

## Local synthetic demo (PowerShell)

```powershell
python -m scripts.seed_demo --database data/demo.db
$env:DATABASE_PATH='data/demo.db'
$env:DASHBOARD_TOKEN=python -c "import secrets; print(secrets.token_urlsafe(32))"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Read the generated token with `$env:DASHBOARD_TOKEN` and copy it into the login form. Use a
separate demo database: the seed command refuses to modify existing real jobs.
All sample rows and findings are labeled DEMO. Screenshots under `assets/`
depict synthetic data, not actual GitHub reviews.
