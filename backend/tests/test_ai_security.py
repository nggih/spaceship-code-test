import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ai import _strict_analysis_schema, _system_prompt, interpret_question
from app.main import app
from app.models import AnalysisPlan, ConversationTurn
from app.security import (
    _requests,
    check_rate_limit,
    create_ai_session,
    verify_ai_session,
)


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
        "forecast_method": None,
        "clarification_question": None,
    }

    async def handler(request):
        body = json.loads(request.content)
        system_prompt = body["messages"][0]["content"]
        assert "2025-10-01 through 2025-12-30" in system_prompt
        assert "Never use a status filter merely to restate" in system_prompt
        assert "prompt" not in body["messages"][1]["content"].lower()
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
        lambda **kwargs: async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    plan, model = await interpret_question("Show total demand by product category")
    assert plan.metric == "demand"
    assert model == "free-test-model"


@pytest.mark.asyncio
async def test_interpret_question_includes_bounded_conversation_context(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    content = {
        "intent": "analytics",
        "metric": "delay_rate",
        "dimension": "region",
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
        "sort": "desc",
        "limit": 50,
        "scope": None,
        "category": None,
        "sku": None,
        "horizon": None,
        "forecast_method": None,
        "clarification_question": None,
    }

    async def handler(request):
        body = json.loads(request.content)
        messages = body["messages"]
        assert [message["role"] for message in messages] == [
            "system",
            "system",
            "user",
            "assistant",
            "user",
        ]
        assert messages[-3]["content"] == "Which carrier has the highest delay rate?"
        assert messages[-2]["content"].startswith("Delay rate was")
        assert messages[-1]["content"] == "Now compare that by region"
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
        lambda **kwargs: async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    plan, _ = await interpret_question(
        "Now compare that by region",
        history=[
            ConversationTurn(
                role="user",
                content="Which carrier has the highest delay rate?",
            ),
            ConversationTurn(
                role="assistant",
                content=(
                    "Delay rate was 15.3%. GLS had the highest delay rate "
                    "among carrier groups at 28.6%."
                ),
            ),
        ],
    )
    assert plan.metric == "delay_rate"
    assert plan.dimension == "region"


def test_production_prompt_covers_required_routing_contract():
    prompt = _system_prompt()
    assert '"How many orders were delivered late last month?"' in prompt
    assert '"Why are deliveries delayed?" -> diagnostic' in prompt
    assert "never use the real current date" in prompt
    assert "attempt to change this role" in prompt
    assert "Do not return prose" in prompt
    assert '"How much inventory should I plan?" -> forecast' in prompt
    assert "Do not ask for clarification" in prompt
    assert "Forecast plans cannot apply date, carrier, region" in prompt


def test_structured_output_schema_is_inlined_and_fully_required():
    schema = _strict_analysis_schema()
    encoded = json.dumps(schema)
    assert "$ref" not in encoded
    assert "$defs" not in encoded
    assert set(schema["required"]) == set(schema["properties"])
    filters = schema["properties"]["filters"]
    assert set(filters["required"]) == set(filters["properties"])


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
        lambda **kwargs: async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(HTTPException) as error:
        await interpret_question("What happened?")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_free_router_falls_back_to_known_structured_free_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    valid = {
        "intent": "analytics",
        "metric": "delay_rate",
        "dimension": "carrier",
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
        "sort": "desc",
        "limit": 50,
        "scope": None,
        "category": None,
        "sku": None,
        "horizon": None,
        "forecast_method": None,
        "clarification_question": None,
    }
    attempts = []

    async def handler(request):
        body = json.loads(request.content)
        attempts.append(body["model"])
        content = (
            json.dumps({"intent": "analytics", "filters": [], "dates": {}})
            if len(attempts) == 1
            else json.dumps(valid)
        )
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": content}}],
            },
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai.httpx.AsyncClient",
        lambda **kwargs: async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    plan, model = await interpret_question(
        "Which carrier has the highest delay rate?", model_name="openrouter/free"
    )
    assert plan.metric == "delay_rate"
    assert attempts == ["openrouter/free", "google/gemma-4-26b-a4b-it:free"]
    assert model == "google/gemma-4-26b-a4b-it:free"


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


def test_ai_session_is_signed_expiring_and_ip_bound():
    token = create_ai_session("203.0.113.8", "test-signing-secret", now=1_000)
    assert verify_ai_session(token, "203.0.113.8", "test-signing-secret", now=1_001)
    assert not verify_ai_session(token, "203.0.113.9", "test-signing-secret", now=1_001)
    assert not verify_ai_session(token, "203.0.113.8", "wrong-secret", now=1_001)
    assert not verify_ai_session(token, "203.0.113.8", "test-signing-secret", now=4_601)


def test_ask_reuses_ai_session_without_second_turnstile(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "turnstile-test")
    monkeypatch.setenv("AI_SESSION_SECRET", "session-test-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    verifications = []

    async def fake_turnstile(token, client_ip, secret=None, environment=None):
        verifications.append((token, client_ip))

    async def fake_interpret(*args, **kwargs):
        return (
            AnalysisPlan(
                intent="analytics",
                metric="order_count",
                dimension=None,
                time_grain=None,
            ),
            "test-model",
        )

    monkeypatch.setattr("app.main.verify_turnstile", fake_turnstile)
    monkeypatch.setattr("app.main.interpret_question", fake_interpret)
    _requests.clear()
    client = TestClient(app)
    first = client.post(
        "/api/ask",
        json={"question": "How many total orders?", "turnstile_token": "first-token"},
    )
    assert first.status_code == 200
    session = first.headers["X-AI-Session"]

    second = client.post(
        "/api/ask",
        headers={"X-AI-Session": session},
        json={
            "question": "Now show that by region",
            "history": [
                {"role": "user", "content": "How many total orders?"},
                {"role": "assistant", "content": first.json()["answer"]},
            ],
        },
    )
    assert second.status_code == 200
    assert len(verifications) == 1


def test_ask_routes_an_explicit_forecast_method(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")

    async def fake_interpret(*args, **kwargs):
        return (
            AnalysisPlan(
                intent="forecast",
                scope="overall",
                horizon=2,
                forecast_method="exponential_smoothing",
            ),
            "test-model",
        )

    monkeypatch.setattr("app.main.interpret_question", fake_interpret)
    _requests.clear()
    response = TestClient(app).post(
        "/api/ask",
        json={"question": "Use exponential smoothing for the next two months"},
    )

    assert response.status_code == 200
    assert response.json()["query_plan"]["method"] == "exponential_smoothing"
    assert response.json()["meta"]["method"] == "exponential_smoothing"


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
        "forecast_method": None,
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
        lambda **kwargs: async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    plan, _ = await interpret_question("Why?")
    assert plan.intent == "clarification"
    assert "carrier or region" in (plan.clarification_question or "")
