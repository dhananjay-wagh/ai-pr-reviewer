import json
from fastapi import FastAPI , Request, HTTPException
from app.utils import verify_signature, fetch_pr_diff,get_code_review, post_inline_comment, add_labels

app = FastAPI()

@app.post("/webhook")
async def webhook(request : Request):

    event = request.headers.get("x-github-event")
    if event != "pull_request":
        return {
            "status": "ignored"
        }
    
    payload = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not signature:
        raise HTTPException(status_code=403, detail="missing signature")

    data = json.loads(payload)

    action = data.get("action")
    if action != "opened":
        return {
            "status":"ignored"
        }
    
    if verify_signature(payload, signature):
        pass
    else:
        raise HTTPException(status_code=403, detail="invalid signature")

    repo = data["repository"]["full_name"]
    pr_number = data["pull_request"]["number"]


    diff = await fetch_pr_diff(repo, pr_number)
    if diff is None:
        print("Failed to retrive the Diff from Github API")
        return None
    if not diff:
        print("No change")
        return None

    diff = diff[:8000]

    commit_sha = data["pull_request"]["head"]["sha"]
    reviews = await get_code_review(diff)

    if reviews is None:
        print("Skipping -- Groq response was invalid")
        return {
            "status" : "error parsing review"
        }
  
    for item in reviews:
        await post_inline_comment(
            repo,
            pr_number,
            commit_sha,
            item["file"],
            item["line"],
            item["comment"]
        )

    if reviews:
        await add_labels(repo, pr_number, "needs changes")
    else:
        await add_labels(repo, pr_number, 'approved')
        
    return {
        "status" : "received"
    }