from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from .data import DATA_MAX_DATE, DATA_MIN_DATE, metadata
from .models import AnalysisPlan

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _system_prompt() -> str:
    data = metadata()
    return f"""You interpret logistics analytics questions into a validated query plan.
You do not calculate results and you never produce SQL.
Dataset order_date range: {DATA_MIN_DATE} through {DATA_MAX_DATE}.
Treat {DATA_MAX_DATE} as today for relative dates such as last month.
Allowed values: {json.dumps(data['filters'])}.
“Late” means status delayed. Forecasting supports overall or product category only.
Return only the requested JSON schema."""


def deterministic_fallback(question: str) -> AnalysisPlan | None:
    """Cover the documented query subset when free-model output is malformed."""
    normalized = re.sub(r"\s+", " ", question.lower().strip())
    if "delayed orders" in normalized and "by week" in normalized:
        start = DATA_MAX_DATE - timedelta(days=92)
        return AnalysisPlan(
            intent="analytics",
            metric="delayed_orders",
            dimension="week",
            time_grain="week",
            filters={
                "start_date": start,
                "end_date": DATA_MAX_DATE,
                "statuses": ["delayed"],
            },
        )
    if "carrier" in normalized and "highest delay rate" in normalized:
        return AnalysisPlan(
            intent="analytics",
            metric="delay_rate",
            dimension="carrier",
            sort="desc",
            limit=9,
        )
    if (
        ("delivered late" in normalized or "late orders" in normalized)
        and "last month" in normalized
    ):
        current_month = DATA_MAX_DATE.replace(day=1)
        end = current_month - timedelta(days=1)
        start = date(end.year, end.month, 1)
        return AnalysisPlan(
            intent="analytics",
            metric="delayed_orders",
            filters={
                "start_date": start,
                "end_date": end,
                "statuses": ["delayed"],
            },
        )
    return None


async def interpret_question(
    question: str,
    api_key: str | None = None,
    model_name: str | None = None,
    public_app_url: str | None = None,
) -> tuple[AnalysisPlan, str]:
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI interpretation is not configured.")
    supported_plan = deterministic_fallback(question)
    if supported_plan:
        return supported_plan, "validated-supported-query-parser"
    schema = AnalysisPlan.model_json_schema()
    request_body = {
        "model": model_name or os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": question},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "analysis_plan",
                "strict": True,
                "schema": schema,
            },
        },
        "provider": {"require_parameters": True},
        "temperature": 0,
        "max_tokens": 700,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": public_app_url
        or os.getenv("PUBLIC_APP_URL", "http://localhost:5173"),
        "X-Title": "Logistics Intelligence",
    }
    last_error: Exception | None = None
    for attempt in range(2):
        if attempt:
            request_body["messages"] = [
                *request_body["messages"],
                {
                    "role": "system",
                    "content": "Retry: return exactly one JSON object matching the schema, with no prose.",
                },
            ]
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    OPENROUTER_URL, headers=headers, json=request_body
                )
        except httpx.TimeoutException as exc:
            last_error = exc
            continue
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503, detail="The AI service is unavailable."
            ) from exc

        if response.status_code in {402, 429}:
            raise HTTPException(
                status_code=503,
                detail="Free AI capacity is currently unavailable. Please try again later.",
            )
        if response.status_code >= 400:
            last_error = ValueError(f"OpenRouter status {response.status_code}")
            continue
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            plan = AnalysisPlan.model_validate_json(content)
            return plan, payload.get("model", request_body["model"])
        except (ValueError, KeyError, IndexError, ValidationError) as exc:
            last_error = exc

    fallback = deterministic_fallback(question)
    if fallback:
        return fallback, "deterministic-fallback-after-openrouter"
    if isinstance(last_error, httpx.TimeoutException):
        raise HTTPException(status_code=503, detail="The free AI model timed out.")
    raise HTTPException(
        status_code=502, detail="The AI returned an invalid analytical plan."
    ) from last_error
