import os
os.environ["GITHUB_WEBHOOK_SECRET"] = 'test-secret'

import hmac
import hashlib
from app.utils import verify_signature



def test_valid_signature():
    payload = b"hello"

    expected = "sha256=" + hmac.new("test-secret".encode() , payload, hashlib.sha256).hexdigest()

    assert verify_signature(payload, expected) == True

def test_invalid_signature():
    payload = b"hello"

    assert verify_signature(payload, "sha256=fakehash") == False