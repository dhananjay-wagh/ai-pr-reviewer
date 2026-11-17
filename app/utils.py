"""Webhook authentication; API/model integrations live in dedicated modules."""

import hashlib
import hmac
import os
import re

from dotenv import load_dotenv

load_dotenv()


def verify_signature(payload: bytes, signature: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if (
        not secret
        or not isinstance(signature, str)
        or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature)
    ):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
