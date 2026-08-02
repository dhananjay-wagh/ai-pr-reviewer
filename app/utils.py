import os
import httpx
import json
import groq
from dotenv import load_dotenv
import hmac
import hashlib

load_dotenv()
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def verify_signature(payload : bytes, signature: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return False

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
        valid_reviews = []
        for item in res:
            if isinstance(item.get("file"), str) and item["file"] and isinstance(item.get("line"), int) and item["line"] and isinstance(item.get("comment"), str) and item['comment']:
                valid_reviews.append(item)
            else:
                print(f"Skipping invalid review item : {item}")
        return valid_reviews
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

async def add_labels(repo: str, pr_number: int, label:str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/labels",
            headers= {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            json= {
                "labels": [label]
            }
        )
        return response.status_code