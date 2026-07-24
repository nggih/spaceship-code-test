from __future__ import annotations

import os
import time
from collections import defaultdict, deque

import httpx
from fastapi import HTTPException

_requests: dict[str, deque[float]] = defaultdict(deque)


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
