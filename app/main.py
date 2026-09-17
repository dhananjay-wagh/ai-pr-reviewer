import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.store import Store
from app.utils import verify_signature

app = FastAPI(title="AI Code Reviewer", version="2.0.0")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith(("/api/", "/dashboard")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
    return response


class Head(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class PullRequest(BaseModel):
    number: int = Field(gt=0, strict=True)
    head: Head


class Repository(BaseModel):
    full_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Installation(BaseModel):
    id: int = Field(gt=0, strict=True)


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str
    repository: Repository
    pull_request: PullRequest
    installation: Installation | None = None


def store():
    return Store(os.getenv("DATABASE_PATH", "data/reviewer.db"))


def authorize(request: Request):
    token = os.getenv("DASHBOARD_TOKEN", "")
    if not token or not hmac.compare_digest(
        request.headers.get("authorization", "").encode(), f"Bearer {token}".encode()
    ):
        raise HTTPException(401, "Authentication required")


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(STATIC / "index.html")


@app.get("/api/jobs", dependencies=[Depends(authorize)])
async def jobs(limit: int = Query(50, ge=1, le=100), before: float | None = None):
    return {"jobs": store().recent(limit, before)}


@app.get("/api/metrics", dependencies=[Depends(authorize)])
async def metrics():
    return store().metrics()


@app.get("/api/jobs/{job_id}", dependencies=[Depends(authorize)])
async def job_status(job_id: str):
    job = store().get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(authorize)], status_code=202)
async def retry_job(job_id: str):
    db = store()
    if not db.get(job_id):
        raise HTTPException(404, "Job not found")
    if not db.retry_failed(job_id):
        raise HTTPException(409, "Only failed jobs can be retried")
    return {"status": "queued", "job_id": job_id}


@app.post("/webhook", status_code=202)
async def webhook(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 1_048_576:
            raise HTTPException(413, "Webhook payload too large")
    signature = request.headers.get("x-hub-signature-256")
    if not signature:
        raise HTTPException(403, "missing signature")
    if not verify_signature(bytes(payload), signature):
        raise HTTPException(403, "invalid signature")
    if request.headers.get("x-github-event") != "pull_request":
        return {"status": "ignored"}
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "invalid JSON payload")
    if not isinstance(data, dict):
        raise HTTPException(400, "payload must be an object")
    if data.get("action") not in ("opened", "reopened", "synchronize"):
        return {"status": "ignored"}
    try:
        event = Event.model_validate(data)
    except ValidationError:
        raise HTTPException(422, "Invalid pull request payload")
    if os.getenv("GITHUB_APP_ID") and not event.installation:
        raise HTTPException(422, "GitHub App event requires installation")
    allowed = {
        repo.strip().lower()
        for repo in os.getenv("ALLOWED_REPOSITORIES", "").split(",")
        if repo.strip()
    }
    if allowed and event.repository.full_name.lower() not in allowed:
        raise HTTPException(403, "Repository is not enabled")
    delivery = request.headers.get("x-github-delivery", "")
    if not delivery or len(delivery) > 200:
        raise HTTPException(400, "Missing or invalid delivery ID")
    job_id, created = store().enqueue(
        delivery,
        event.repository.full_name,
        event.pull_request.number,
        event.pull_request.head.sha,
        event.installation.id if event.installation else None,
    )
    return {"status": "queued" if created else "duplicate", "job_id": job_id}
