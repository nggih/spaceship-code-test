from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque

import httpx
from fastapi import HTTPException

_requests: dict[str, deque[float]] = defaultdict(deque)
_login_requests: dict[str, deque[float]] = defaultdict(deque)
AI_SESSION_TTL_SECONDS = 60 * 60


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_ai_session(client_ip: str, secret: str, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    ip_digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:20]
    payload = f"{issued_at}:{ip_digest}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def verify_ai_session(
    token: str | None,
    client_ip: str,
    secret: str | None,
    now: int | None = None,
) -> bool:
    if not token or not secret:
        return False
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _decode(encoded_payload)
        provided_signature = _decode(encoded_signature)
        expected_signature = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(provided_signature, expected_signature):
            return False
        issued_raw, ip_digest = payload.decode("utf-8").split(":", 1)
        issued_at = int(issued_raw)
    except (ValueError, TypeError, UnicodeDecodeError):
        return False
    current = int(time.time() if now is None else now)
    expected_ip = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:20]
    return (
        hmac.compare_digest(ip_digest, expected_ip)
        and issued_at <= current + 60
        and current - issued_at <= AI_SESSION_TTL_SECONDS
    )


async def check_rate_limit(
    client_ip: str,
    binding=None,
    limit: int = 5,
    window: int = 600,
) -> None:
    if binding is not None:
        result = await binding.limit({"key": f"ai:{client_ip}"})
        success = getattr(result, "success", None)
        if success is None and isinstance(result, dict):
            success = result.get("success")
        if not success:
            raise HTTPException(
                status_code=429,
                detail="AI query limit reached. Try again in a minute.",
            )
        # The Cloudflare binding provides a distributed burst guard. Continue
        # through the application window so a warm isolate also enforces the
        # product policy of five AI questions per ten minutes.
    now = time.monotonic()
    bucket = _requests[client_ip]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="AI query limit reached. Try again in a few minutes.",
        )
    bucket.append(now)


async def check_login_rate_limit(
    client_ip: str,
    binding=None,
    limit: int = 5,
    window: int = 900,
) -> None:
    if binding is not None:
        result = await binding.limit({"key": f"login:{client_ip}"})
        success = getattr(result, "success", None)
        if success is None and isinstance(result, dict):
            success = result.get("success")
        if not success:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again later.",
            )
    now = time.monotonic()
    bucket = _login_requests[client_ip]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )
    bucket.append(now)


async def verify_turnstile(
    token: str | None,
    client_ip: str,
    secret: str | None = None,
    environment: str | None = None,
) -> None:
    secret = secret or os.getenv("TURNSTILE_SECRET_KEY")
    if not secret:
        if (environment or os.getenv("ENVIRONMENT", "development")) == "production":
            raise HTTPException(status_code=503, detail="Turnstile is not configured.")
        return
    if not token:
        raise HTTPException(status_code=400, detail="Turnstile verification is required.")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token, "remoteip": client_ip},
            )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Turnstile verification failed.") from exc
    if not payload.get("success"):
        raise HTTPException(status_code=403, detail="Turnstile challenge was not accepted.")
