from fastapi.testclient import TestClient

from app.auth import (
    AuthUser,
    _validate_claims,
    create_credential_session,
    password_policy_errors,
    password_policy_valid,
    verify_credential_session,
)
from app.main import app
from app.models import AnalysisPlan
from app.security import _login_requests, _requests


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


def test_credential_session_is_signed_and_expires():
    token = create_credential_session("reviewer", "session-secret", now=1_000)
    assert verify_credential_session(
        token, "session-secret", "reviewer", now=1_001
    ) == AuthUser(
        subject="credentials:2d70999ae1805e4bcef9b4ab3a4b827f578c61740f30076fcdc35c7ae7f586b3",
        email="reviewer@local.account",
        name="reviewer",
    )
    assert verify_credential_session(token, "wrong-secret", "reviewer", now=1_001) is None
    assert (
        verify_credential_session(token, "session-secret", "other", now=1_001)
        is None
    )
    assert (
        verify_credential_session(token, "session-secret", "reviewer", now=29_800)
        is None
    )


def test_password_policy_requires_length_and_character_classes():
    assert password_policy_valid("Correct-Horse9!")
    assert not password_policy_valid("short")
    assert not password_policy_valid("alllowercase9!")
    assert not password_policy_valid("ALLUPPERCASE9!")
    assert not password_policy_valid("NoNumbersHere!")
    assert not password_policy_valid("NoSymbolsHere9")
    assert not password_policy_valid("Has Whitespace9!")
    assert "at least 12 characters" in password_policy_errors("Short9!")


def test_login_refuses_a_weak_configured_password(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("USERNAME", "reviewer")
    monkeypatch.setenv("PASSWORD", "weak")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "independent-session-secret")
    _login_requests.clear()

    response = TestClient(app).post(
        "/api/auth/login",
        json={"username": "reviewer", "password": "weak"},
    )
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "Configured login password does not meet the security policy."
    )


def test_login_cookie_protects_api_and_logout_revokes_browser_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("USERNAME", "reviewer")
    monkeypatch.setenv("PASSWORD", "Correct-Password9!")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "independent-session-secret")
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "history.db"))
    _login_requests.clear()
    client = TestClient(app)

    assert client.get("/api/auth/me").status_code == 401
    invalid = client.post(
        "/api/auth/login",
        json={"username": "reviewer", "password": "incorrect"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid username or password."

    login = client.post(
        "/api/auth/login",
        json={"username": "reviewer", "password": "Correct-Password9!"},
    )
    assert login.status_code == 200
    assert login.json()["name"] == "reviewer"
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/conversations").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


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
