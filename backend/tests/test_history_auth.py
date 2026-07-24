from fastapi.testclient import TestClient

from app.auth import AuthUser, _validate_claims
from app.main import app
from app.models import AnalysisPlan
from app.security import _requests


def test_access_claim_validation():
    user = _validate_claims(
        {
            "iss": "https://team.cloudflareaccess.com",
            "aud": ["expected-audience"],
            "sub": "identity-123",
            "email": "reviewer@example.com",
            "exp": 2_000,
            "nbf": 900,
        },
        issuer="https://team.cloudflareaccess.com",
        audience="expected-audience",
        now=1_000,
    )
    assert user == AuthUser(
        subject="identity-123", email="reviewer@example.com", name=None
    )


def test_conversation_lifecycle_is_persistent_and_user_owned(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_AUTH_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test")
    monkeypatch.setenv("TURNSTILE_AFTER_LOGIN", "false")

    async def fake_interpret(*args, **kwargs):
        return (
            AnalysisPlan(
                intent="analytics",
                metric="delay_rate",
                dimension="carrier",
                sort="desc",
            ),
            "test-model",
        )

    monkeypatch.setattr("app.main.interpret_question", fake_interpret)
    _requests.clear()
    client = TestClient(app)

    answer = client.post(
        "/api/ask",
        json={"question": "Which carrier has the highest delay rate?"},
    )
    assert answer.status_code == 200
    conversation_id = answer.json()["meta"]["conversation_id"]

    listing = client.get("/api/conversations").json()["conversations"]
    assert listing[0]["id"] == conversation_id
    assert listing[0]["message_count"] == 2
    assert listing[0]["title"] == "Which carrier has the highest delay rate?"

    detail = client.get(f"/api/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
    ]
    assert detail.json()["messages"][1]["result"]["kind"] == "result"

    renamed = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Carrier delays"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Carrier delays"

    other_user = client.get(
        f"/api/conversations/{conversation_id}",
        headers={"X-Dev-User": "other@example.com"},
    )
    assert other_user.status_code == 404

    deleted = client.delete(f"/api/conversations/{conversation_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
