import json
from fastapi import FastAPI , Request, HTTPException
from app.utils import verify_signature, fetch_pr_diff,get_code_review, post_inline_comment, add_labels
from app.reviews import validate_locations

app = FastAPI()

@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }



@app.post("/webhook")
async def webhook(request: Request):
    event = request.headers.get("x-github-event")
    if event != "pull_request":
        return {
            "status": "ignored"
        }

    payload = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not signature:
        raise HTTPException(status_code=403, detail="missing signature")

    if not verify_signature(payload, signature):
        raise HTTPException(status_code=403, detail="invalid signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON payload")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    action = data.get("action")
    if action not in ["opened", "synchronize", "reopened"]:
        return {
            "status": "ignored"
        }

    repo = data.get("repository", {}).get("full_name")
    pr_data = data.get("pull_request", {})
    pr_number = pr_data.get("number")
    commit_sha = pr_data.get("head", {}).get("sha")

    if not repo or not pr_number or not commit_sha:
        return {
            "status": "missing pull request data"
        }

    diff = await fetch_pr_diff(repo, pr_number)
    if diff is None:
        print("Failed to retrieve the Diff from Github API")
        return {
            "status": "failed to retrieve diff"
        }
    if not diff:
        print("No change")
        return {
            "status": "no diff"
        }

    if len(diff) > 8000:
        raise HTTPException(status_code=422, detail="diff exceeds review limit; no approval issued")

    reviews = await get_code_review(diff)

    if reviews is None:
        print("Skipping -- Groq response was invalid")
        return {
            "status": "error parsing review"
        }

    try:
        validate_locations(reviews, diff)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    for item in reviews:
        result = await post_inline_comment(
            repo,
            pr_number,
            commit_sha,
            item["file"],
            item["line"],
            item["comment"],
            item.get("side", "RIGHT")
        )
        if result != 201:
            raise HTTPException(status_code=502, detail="failed to publish comment")

    if reviews:
        result = await add_labels(repo, pr_number, "needs changes")
    else:
        result = await add_labels(repo, pr_number, "approved")
    if result != 200:
        raise HTTPException(status_code=502, detail="failed to publish label")

    return {
        "status": "received"
    }
