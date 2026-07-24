from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Response

from .ai import interpret_question
from .analytics import dashboard_payload, run_analytics
from .data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS, metadata
from .forecast import run_forecast
from .models import AnalyticsQuery, AnalyticsResponse, AskRequest, ForecastQuery
from .security import check_rate_limit, verify_turnstile

app = FastAPI(
    title="Logistics Intelligence API",
    version="0.1.0",
    description="Validated, read-only analytics for the logistics assignment dataset.",
)

def _binding(request: Request, name: str, default: str | None = None) -> str | None:
    worker_env = request.scope.get("env")
    if worker_env is not None:
        value = getattr(worker_env, name, None)
        if value is not None:
            return str(value)
    return os.getenv(name, default)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed_origins = {
        value.strip()
        for value in (
            _binding(
                request,
                "ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
            or ""
        ).split(",")
        if value.strip()
    }
    if origin and origin not in allowed_origins:
        return Response(status_code=403, content="Origin is not allowed.")
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        if int(request.headers.get("content-length", "0") or "0") > 16_384:
            return Response(status_code=413, content="Request body is too large.")
        response = await call_next(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request.headers.get(
        "X-Request-ID", str(uuid.uuid4())
    )
    return response


@app.get("/api/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "dataset_rows": len(ORDERS),
        "data_min_date": DATA_MIN_DATE,
        "data_max_date": DATA_MAX_DATE,
        "ai_configured": bool(_binding(request, "OPENROUTER_API_KEY")),
    }


@app.get("/api/metadata")
def get_metadata() -> dict[str, object]:
    return metadata()


@app.post("/api/dashboard")
def get_dashboard(query: AnalyticsQuery) -> dict[str, object]:
    return dashboard_payload(query)


@app.post("/api/analytics", response_model=AnalyticsResponse)
def analytics(query: AnalyticsQuery) -> AnalyticsResponse:
    try:
        return run_analytics(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/forecast", response_model=AnalyticsResponse)
def forecast(query: ForecastQuery) -> AnalyticsResponse:
    try:
        return run_forecast(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ask", response_model=AnalyticsResponse)
async def ask(payload: AskRequest, request: Request) -> AnalyticsResponse:
    client_ip = (
        request.headers.get("CF-Connecting-IP")
        or (request.client.host if request.client else "unknown")
    )
    await verify_turnstile(
        payload.turnstile_token,
        client_ip,
        secret=_binding(request, "TURNSTILE_SECRET_KEY"),
        environment=_binding(request, "ENVIRONMENT", "development"),
    )
    check_rate_limit(client_ip)
    plan, model = await interpret_question(
        payload.question,
        api_key=_binding(request, "OPENROUTER_API_KEY"),
        model_name=_binding(request, "OPENROUTER_MODEL", "openrouter/free"),
        public_app_url=_binding(request, "PUBLIC_APP_URL", "http://localhost:5173"),
    )
    try:
        if plan.intent == "forecast":
            result = run_forecast(
                ForecastQuery(
                    scope=plan.scope or "overall",
                    category=plan.category,
                    horizon=plan.horizon or 3,
                )
            )
        else:
            result = run_analytics(
                AnalyticsQuery(
                    metric=plan.metric or "order_count",
                    dimension=plan.dimension,
                    time_grain=plan.time_grain,
                    filters=plan.filters,
                    sort=plan.sort,
                    limit=plan.limit,
                )
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result.meta.update({"model": model, "question": payload.question})
    return result
