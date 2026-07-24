import json

import httpx
import pytest
from fastapi import HTTPException

from app.ai import interpret_question
from app.security import _requests, check_rate_limit


@pytest.mark.asyncio
async def test_interpret_question_valid(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    content = {
        "intent": "analytics",
        "metric": "demand",
        "dimension": "category",
        "time_grain": None,
        "filters": {
            "start_date": "2025-10-01",
            "end_date": "2025-12-30",
            "carriers": [],
            "regions": [],
            "warehouses": [],
            "categories": [],
            "skus": [],
            "statuses": [],
        },
        "sort": "asc",
        "limit": 50,
        "scope": None,
        "category": None,
        "sku": None,
        "horizon": None,
        "clarification_question": None,
    }

    async def handler(request):
        return httpx.Response(
            200,
            json={
                "model": "free-test-model",
                "choices": [{"message": {"content": json.dumps(content)}}],
            },
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai.httpx.AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    plan, model = await interpret_question("Show total demand by product category")
    assert plan.metric == "demand"
    assert model == "free-test-model"


@pytest.mark.asyncio
async def test_interpret_question_rejects_malformed(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    async def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "not json"}}]}
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai.httpx.AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    with pytest.raises(HTTPException) as error:
        await interpret_question("What happened?")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_rate_limit():
    _requests.clear()
    for _ in range(5):
        await check_rate_limit("test-ip")
    with pytest.raises(HTTPException) as error:
        await check_rate_limit("test-ip")
    assert error.value.status_code == 429


@pytest.mark.asyncio
async def test_cloudflare_rate_limit_binding():
    class Binding:
        async def limit(self, payload):
            assert payload == {"key": "ai:203.0.113.5"}
            return {"success": False}

    _requests.clear()
    with pytest.raises(HTTPException) as error:
        await check_rate_limit("203.0.113.5", binding=Binding())
    assert error.value.status_code == 429


@pytest.mark.asyncio
async def test_cloudflare_binding_still_enforces_ten_minute_app_window():
    class Binding:
        async def limit(self, payload):
            return {"success": True}

    _requests.clear()
    for _ in range(5):
        await check_rate_limit("198.51.100.9", binding=Binding())
    with pytest.raises(HTTPException) as error:
        await check_rate_limit("198.51.100.9", binding=Binding())
    assert error.value.status_code == 429


@pytest.mark.asyncio
async def test_interpret_question_can_request_clarification(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    content = {
        "intent": "clarification",
        "metric": None,
        "dimension": None,
        "time_grain": None,
        "filters": {
            "start_date": None,
            "end_date": None,
            "carriers": [],
            "regions": [],
            "warehouses": [],
            "categories": [],
            "skus": [],
            "statuses": [],
        },
        "sort": "asc",
        "limit": 50,
        "scope": None,
        "category": None,
        "sku": None,
        "horizon": None,
        "clarification_question": "Which carrier or region should I compare?",
    }

    async def handler(request):
        return httpx.Response(
            200,
            json={
                "model": "free-test-model",
                "choices": [{"message": {"content": json.dumps(content)}}],
            },
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai.httpx.AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    plan, _ = await interpret_question("Why?")
    assert plan.intent == "clarification"
    assert "carrier or region" in (plan.clarification_question or "")
