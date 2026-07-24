from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request


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
    if int(payload.get("exp", 0)) <= current or int(payload.get("nbf", 0)) > current + 60:
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
        from js import Object, Uint8Array, crypto, fetch  # type: ignore[import-not-found]
        from pyodide.ffi import to_js  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cloudflare Access verification requires the Worker runtime.",
        ) from exc

    kid = header.get("kid")
    if header.get("alg") != "RS256" or not isinstance(kid, str):
        raise HTTPException(status_code=401, detail="Unsupported authentication token.")
    response = await fetch(f"{team_domain}/cdn-cgi/access/certs")
    if not response.ok:
        raise HTTPException(status_code=503, detail="Unable to verify authentication.")
    jwks = (await response.json()).to_py()
    jwk = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
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
        Uint8Array.new(signature),
        Uint8Array.new(signed),
    )
    if not bool(valid):
        raise HTTPException(status_code=401, detail="Invalid authentication signature.")


async def require_user(request: Request) -> AuthUser:
    environment = _binding(request, "ENVIRONMENT", "development")
    if environment != "production":
        email = request.headers.get("X-Dev-User") or _binding(
            request, "DEV_AUTH_EMAIL", "reviewer@local.test"
        )
        return AuthUser(subject=f"local:{email}", email=email or "reviewer@local.test")

    team_domain = (_binding(request, "ACCESS_TEAM_DOMAIN") or "").rstrip("/")
    audience = _binding(request, "ACCESS_AUD")
    if not team_domain or not audience:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if not token:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    try:
        encoded_header, encoded_payload, _ = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc
    header = _decode_segment(encoded_header)
    payload = _decode_segment(encoded_payload)
    await _verify_access_signature(token, header, team_domain)
    return _validate_claims(payload, issuer=team_domain, audience=audience)
