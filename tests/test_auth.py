from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import github_for_job


@pytest.mark.anyio
async def test_app_signs_jwt_and_uses_installation_token(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "key.pem"
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", str(path))
    with patch("app.auth.GitHub") as cls:
        cls.return_value.request = AsyncMock(side_effect=[{"slug": "reviewer"}, {"token": "installation-token"}])
        await github_for_job({"installation": 42})
        signed = cls.call_args_list[0].args[0]
        claims = jwt.decode(signed, key.public_key(), algorithms=["RS256"])
        assert claims["iss"] == "123"
        assert claims["exp"] - claims["iat"] == 600
        assert cls.call_args_list[1].args == ("installation-token",)
        assert cls.call_args_list[1].kwargs["bot_login"] == "reviewer[bot]"
        assert cls.return_value.request.call_args_list[1].args[:2] == ("POST", "/app/installations/42/access_tokens")


@pytest.mark.anyio
async def test_app_mode_never_falls_back_to_personal_token(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_TOKEN", "pat")
    with pytest.raises(ValueError, match="installation"):
        await github_for_job({})
