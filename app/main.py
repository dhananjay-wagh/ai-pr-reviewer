import hmac
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.store import Store
from app.utils import verify_signature

app = FastAPI(title="AI Code Reviewer", version="2.0.0")


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
    if not token or not hmac.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
        raise HTTPException(401, "Authentication required")


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/jobs/{job_id}", dependencies=[Depends(authorize)])
async def job_status(job_id: str):
    job = store().get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


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
    delivery = request.headers.get("x-github-delivery", "")
    if not delivery or len(delivery) > 200:
        raise HTTPException(400, "Missing or invalid delivery ID")
    job_id, created = store().enqueue(delivery, event.repository.full_name,
                                    event.pull_request.number, event.pull_request.head.sha,
                                    event.installation.id if event.installation else None)
    return {"status": "queued" if created else "duplicate", "job_id": job_id}
