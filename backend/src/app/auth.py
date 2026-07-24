from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

_jwks_cache: dict[str, Any] = {"expires_at": 0.0, "keys": []}
AUTH_COOKIE_NAME = "logistics_session"
AUTH_SESSION_TTL_SECONDS = 8 * 60 * 60
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


@dataclass(frozen=True)
class AuthUser:
    subject: str
    email: str
    name: str | None = None


def _binding(request: Request, name: str, default: str | None = None) -> str | None:
    worker_env = request.scope.get("env")
    if worker_env is not None:
        value = getattr(worker_env, name, None)
        if value is not None:
            return str(value)
    return os.getenv(name, default)


def _decode_segment(value: str) -> dict[str, Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_bytes(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def credential_subject(username: str) -> str:
    digest = hashlib.sha256(username.casefold().encode("utf-8")).hexdigest()
    return f"credentials:{digest}"


def password_policy_errors(password: str) -> tuple[str, ...]:
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"at most {PASSWORD_MAX_LENGTH} characters")
    if not any(character.islower() for character in password):
        errors.append("a lowercase letter")
    if not any(character.isupper() for character in password):
        errors.append("an uppercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("a number")
    if not any(
        not character.isalnum() and not character.isspace()
        for character in password
    ):
        errors.append("a symbol")
    if any(character.isspace() for character in password):
        errors.append("no whitespace")
    return tuple(errors)


def password_policy_valid(password: str | None) -> bool:
    return bool(password) and not password_policy_errors(password)


def create_credential_session(
    username: str,
    secret: str,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = json.dumps(
        {
            "sub": credential_subject(username),
            "username": username,
            "iat": issued_at,
            "exp": issued_at + AUTH_SESSION_TTL_SECONDS,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_encode_bytes(payload)}.{_encode_bytes(signature)}"


def verify_credential_session(
    token: str | None,
    secret: str | None,
    expected_username: str | None,
    now: int | None = None,
) -> AuthUser | None:
    if not token or not secret or not expected_username:
        return None
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload_bytes = _decode_bytes(encoded_payload)
        provided_signature = _decode_bytes(encoded_signature)
        expected_signature = hmac.new(
            secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
        payload = json.loads(payload_bytes)
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        username = payload["username"]
        subject = payload["sub"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    current = int(time.time() if now is None else now)
    if (
        not isinstance(username, str)
        or not hmac.compare_digest(username, expected_username)
        or subject != credential_subject(expected_username)
        or issued_at > current + 60
        or expires_at <= current
        or expires_at - issued_at != AUTH_SESSION_TTL_SECONDS
    ):
        return None
    email = username if "@" in username else f"{username}@local.account"
    return AuthUser(subject=subject, email=email, name=username)


def _validate_claims(
    payload: dict[str, Any],
    *,
    issuer: str,
    audience: str,
    now: int | None = None,
) -> AuthUser:
    current = int(time.time() if now is None else now)
    token_audience = payload.get("aud", [])
    audiences = (
        [token_audience] if isinstance(token_audience, str) else token_audience
    )
    if payload.get("iss") != issuer or audience not in audiences:
        raise HTTPException(status_code=401, detail="Authentication token is not valid here.")
    expires_at = payload.get("exp")
    not_before = payload.get("nbf", 0)
    if not isinstance(expires_at, (int, float)) or expires_at <= current:
        raise HTTPException(status_code=401, detail="Authentication session has expired.")
    if isinstance(not_before, (int, float)) and not_before > current + 60:
        raise HTTPException(status_code=401, detail="Authentication session has expired.")
    subject = payload.get("sub")
    email = payload.get("email")
    if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
        raise HTTPException(status_code=401, detail="Authentication identity is incomplete.")
    name = payload.get("name")
    return AuthUser(
        subject=subject[:200],
        email=email[:320],
        name=name[:200] if isinstance(name, str) else None,
    )


async def _verify_access_signature(
    token: str,
    header: dict[str, Any],
    team_domain: str,
) -> None:
    """Verify an Access RS256 JWT with Web Crypto in the Python Worker runtime."""
    try:
        from js import Object, crypto, fetch  # type: ignore[import-not-found]
        from pyodide.ffi import to_js  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cloudflare Access verification requires the Worker runtime.",
        ) from exc

    kid = header.get("kid")
    if header.get("alg") != "RS256" or not isinstance(kid, str):
        raise HTTPException(status_code=401, detail="Unsupported authentication token.")
    keys = _jwks_cache["keys"] if _jwks_cache["expires_at"] > time.time() else []
    jwk = next((key for key in keys if key.get("kid") == kid), None)
    if jwk is None:
        response = await fetch(f"{team_domain}/cdn-cgi/access/certs")
        if not response.ok:
            raise HTTPException(status_code=503, detail="Unable to verify authentication.")
        jwks = (await response.json()).to_py()
        keys = jwks.get("keys", [])
        _jwks_cache.update({"expires_at": time.time() + 3600, "keys": keys})
        jwk = next((key for key in keys if key.get("kid") == kid), None)
    if jwk is None:
        raise HTTPException(status_code=401, detail="Authentication signing key is unknown.")

    encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    signature = base64.urlsafe_b64decode(
        encoded_signature + "=" * (-len(encoded_signature) % 4)
    )
    signed = f"{encoded_header}.{encoded_payload}".encode("ascii")
    algorithm = to_js(
        {"name": "RSASSA-PKCS1-v1_5"},
        dict_converter=Object.fromEntries,
    )
    public_key = await crypto.subtle.importKey(
        "jwk",
        to_js(jwk, dict_converter=Object.fromEntries),
        algorithm,
        False,
        ["verify"],
    )
    valid = await crypto.subtle.verify(
        algorithm,
        public_key,
        to_js(signature),
        to_js(signed),
    )
    if not bool(valid):
        raise HTTPException(status_code=401, detail="Invalid authentication signature.")


async def require_user(request: Request) -> AuthUser:
    environment = _binding(request, "ENVIRONMENT", "development")
    team_domain = (_binding(request, "ACCESS_TEAM_DOMAIN") or "").rstrip("/")
    audience = _binding(request, "ACCESS_AUD")
    access_token = request.headers.get("Cf-Access-Jwt-Assertion")
    if team_domain and audience and access_token:
        try:
            encoded_header, encoded_payload, _ = access_token.split(".", 2)
        except ValueError as exc:
            raise HTTPException(
                status_code=401, detail="Invalid authentication token."
            ) from exc
        header = _decode_segment(encoded_header)
        payload = _decode_segment(encoded_payload)
        await _verify_access_signature(access_token, header, team_domain)
        return _validate_claims(payload, issuer=team_domain, audience=audience)

    configured_username = _binding(request, "USERNAME")
    configured_password = _binding(request, "PASSWORD")
    credentials_configured = bool(configured_username and configured_password)
    session_secret = _binding(request, "AUTH_SESSION_SECRET")
    if environment != "production" and not session_secret:
        session_secret = configured_password
    credential_user = verify_credential_session(
        request.cookies.get(AUTH_COOKIE_NAME),
        session_secret,
        configured_username if credentials_configured else None,
    )
    if credential_user is not None:
        return credential_user

    auth_bypass = (_binding(request, "AUTH_BYPASS", "false") or "false").lower()
    if environment != "production" and (
        auth_bypass == "true"
        or not credentials_configured
    ):
        email = request.headers.get("X-Dev-User") or _binding(
            request, "DEV_AUTH_EMAIL", "reviewer@local.test"
        )
        return AuthUser(subject=f"local:{email}", email=email or "reviewer@local.test")

    raise HTTPException(status_code=401, detail="Sign in is required.")
