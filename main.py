import os
import json
from fastapi import FastAPI , Request, HTTPException
import httpx
from dotenv import load_dotenv
import hmac
import hashlib
import groq

load_dotenv()
app = FastAPI()

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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

    return {
        "status" : "received"
    }


def verify_signature(payload : bytes, signature: str) -> bool:
    secret = GITHUB_WEBHOOK_SECRET.encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()  #hexdigest() = This converts those raw bytes into a hexadecimal string.
    return hmac.compare_digest(expected, signature)


async def fetch_pr_diff(repo: str, pr_number: int) ->str | None:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers= {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.diff"
            }
        )

        if response.status_code != 200:
            print(f"Github API error : {response.status_code}")
            return None

        return response.text

async def get_code_review(diff: str)-> list:
    client = groq.AsyncGroq(
        api_key = GROQ_API_KEY
    )

    chat_completions = await client.chat.completions.create(
        messages= [
            {
                "role": "system",
                "content": "You are an expert code reviewer. Review the PR diff and return ONLY a JSON array. Each object must have exactly three keys: `file` (filename), `line` (line number as integer), `comment` (your feedback). Return no other text, no markdown, no explanation. Only the JSON array."
            },
            {
                "role": "user",
                "content": diff
            }
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.7
    )
    response = chat_completions.choices[0].message.content

    try:
        res = json.loads(response)
        return res
    except json.JSONDecodeError as e:
        print(f"error parsing Groq response : {e}")
        return None

async def post_inline_comment(repo: str, pr_number: int, commit_sha: str, file: str, line: int, comment: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments",
            headers= {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            json= {
                "body": comment,
                "commit_id": commit_sha,
                "path": file,
                "line": line,
                "side": "RIGHT"
            }
        )
        if response.status_code != 201:
            print(f"Github API error : {response.status_code}")
            return None

        return response.status_code