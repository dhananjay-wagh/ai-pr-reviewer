"""Short-lived GitHub App installation tokens, or explicit local PAT mode."""
import os
from pathlib import Path
import time

import jwt

from app.github import GitHub


async def github_for_job(job) -> GitHub:
    app_id = os.getenv("GITHUB_APP_ID")
    if not app_id:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("Configure GitHub App credentials or GITHUB_TOKEN")
        return GitHub(token)
    if not job.get("installation"):
        raise ValueError("GitHub App webhook requires an installation ID")
    key = Path(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]).read_bytes()
    now = int(time.time())
    signed = jwt.encode({"iat": now-60, "exp": now+540, "iss": app_id}, key, algorithm="RS256")
    app = GitHub(signed)
    metadata = await app.request("GET", "/app")
    token = await app.request("POST", f"/app/installations/{job['installation']}/access_tokens", json={})
    return GitHub(token["token"], bot_login=f"{metadata['slug']}[bot]")
