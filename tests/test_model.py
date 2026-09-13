from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.model import ModelError, generate


def response(content="[]", finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))],
                           usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3))


@pytest.mark.anyio
async def test_model_validates_and_records_real_usage(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "mock")
    with patch("app.model.groq.AsyncGroq") as cls:
        cls.return_value.__aenter__.return_value.chat.completions.create = AsyncMock(return_value=response())
        result = await generate("diff")
    assert result.findings == []
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 3


@pytest.mark.anyio
@pytest.mark.parametrize("reply,exception", [(response(finish="length"), ModelError),
    (response('[{"file":"a.py","line":true,"comment":"bad"}]'), ValueError)])
async def test_incomplete_or_invalid_model_output_fails(monkeypatch, reply, exception):
    monkeypatch.setenv("GROQ_API_KEY", "mock")
    with patch("app.model.groq.AsyncGroq") as cls:
        cls.return_value.__aenter__.return_value.chat.completions.create = AsyncMock(return_value=reply)
        with pytest.raises(exception):
            await generate("diff")
