from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Response

from .ai import DEFAULT_MODEL, interpret_question
from .analytics import dashboard_payload, run_analytics
from .cache import analytics_cache, dashboard_cache, diagnostic_cache, forecast_cache
from .data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS, metadata
from .diagnostic import run_diagnostic
from .forecast import run_forecast
from .models import (
    AnalyticsQuery,
    AnalyticsResponse,
    AskRequest,
    ClarificationResponse,
    DiagnosticQuery,
    ForecastQuery,
)
from .security import (
    check_rate_limit,
    create_ai_session,
    verify_ai_session,
    verify_turnstile,
)

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


def _runtime_binding(request: Request, name: str):
    worker_env = request.scope.get("env")
    return getattr(worker_env, name, None) if worker_env is not None else None


def _cache_key(prefix: str, model) -> str:
    return f"{prefix}:{model.model_dump_json(exclude_none=True)}"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed_origins = {
        value.strip()
        for value in (
            _binding(
                request,
                "ALLOWED_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
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
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-AI-Session"
        response.headers["Access-Control-Expose-Headers"] = "X-AI-Session"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request.headers.get(
        "X-Request-ID", str(uuid.uuid4())
    )
    return response


@app.get("/api/health")
async def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "dataset_rows": len(ORDERS),
        "data_min_date": DATA_MIN_DATE,
        "data_max_date": DATA_MAX_DATE,
        "ai_configured": bool(_binding(request, "OPENROUTER_API_KEY")),
        "cache": {
            "analytics": analytics_cache.stats(),
            "forecast": forecast_cache.stats(),
            "diagnostic": diagnostic_cache.stats(),
            "dashboard": dashboard_cache.stats(),
        },
    }


@app.get("/api/metadata")
async def get_metadata() -> dict[str, object]:
    return metadata()


@app.post("/api/dashboard")
async def get_dashboard(query: AnalyticsQuery) -> dict[str, object]:
    try:
        result, _ = dashboard_cache.get_or_set(
            _cache_key("dashboard", query), lambda: dashboard_payload(query)
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analytics", response_model=AnalyticsResponse)
async def analytics(query: AnalyticsQuery) -> AnalyticsResponse:
    try:
        result, hit = analytics_cache.get_or_set(
            _cache_key("analytics", query), lambda: run_analytics(query)
        )
        return result.model_copy(update={"meta": {**result.meta, "cache_hit": hit}})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/forecast", response_model=AnalyticsResponse)
async def forecast(query: ForecastQuery) -> AnalyticsResponse:
    try:
        result, hit = forecast_cache.get_or_set(
            _cache_key("forecast", query), lambda: run_forecast(query)
        )
        return result.model_copy(update={"meta": {**result.meta, "cache_hit": hit}})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/diagnostics", response_model=AnalyticsResponse)
async def diagnostics(query: DiagnosticQuery) -> AnalyticsResponse:
    try:
        result, hit = diagnostic_cache.get_or_set(
            _cache_key("diagnostic", query), lambda: run_diagnostic(query)
        )
        return result.model_copy(update={"meta": {**result.meta, "cache_hit": hit}})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/ask",
    response_model=AnalyticsResponse | ClarificationResponse,
)
async def ask(
    payload: AskRequest, request: Request, response: Response
) -> AnalyticsResponse | ClarificationResponse:
    client_ip = request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )
    environment = _binding(request, "ENVIRONMENT", "development")
    session_secret = _binding(request, "AI_SESSION_SECRET")
    has_session = verify_ai_session(
        request.headers.get("X-AI-Session"),
        client_ip,
        session_secret,
    )
    if not has_session:
        await verify_turnstile(
            payload.turnstile_token,
            client_ip,
            secret=_binding(request, "TURNSTILE_SECRET_KEY"),
            environment=environment,
        )
        if environment == "production" and not session_secret:
            raise HTTPException(
                status_code=503, detail="AI session signing is not configured."
            )
        if session_secret:
            response.headers["X-AI-Session"] = create_ai_session(
                client_ip, session_secret
            )
    await check_rate_limit(
        client_ip, binding=_runtime_binding(request, "AI_RATE_LIMITER")
    )
    plan, model = await interpret_question(
        payload.question,
        history=payload.history,
        api_key=_binding(request, "OPENROUTER_API_KEY"),
        model_name=_binding(request, "OPENROUTER_MODEL", DEFAULT_MODEL),
        public_app_url=_binding(request, "PUBLIC_APP_URL", "http://localhost:3000"),
    )
    selected_tool = {
        "analytics": "query_logistics_analytics",
        "diagnostic": "analyze_delay_drivers",
        "forecast": "forecast_demand",
        "clarification": "request_clarification",
    }[plan.intent]
    if plan.intent == "clarification":
        return ClarificationResponse(
            message=plan.clarification_question
            or "Please clarify the metric, time range, or business dimension.",
            suggestions=[
                "Show delayed orders by week for the last 3 months",
                "Which carrier has the highest delay rate?",
                "Forecast PAPER demand for the next 3 months",
            ],
            query_plan=plan.model_dump(mode="json"),
            meta={
                "model": model,
                "question": payload.question,
                "tool": selected_tool,
            },
        )
    try:
        if plan.intent == "forecast":
            forecast_query = ForecastQuery(
                scope=plan.scope or "overall",
                category=plan.category,
                sku=plan.sku,
                horizon=plan.horizon or 1,
                method=plan.forecast_method or "auto",
            )
            result, cache_hit = forecast_cache.get_or_set(
                _cache_key("forecast", forecast_query),
                lambda: run_forecast(forecast_query),
            )
        elif plan.intent == "diagnostic":
            diagnostic_query = DiagnosticQuery(filters=plan.filters)
            result, cache_hit = diagnostic_cache.get_or_set(
                _cache_key("diagnostic", diagnostic_query),
                lambda: run_diagnostic(diagnostic_query),
            )
        else:
            analytics_query = AnalyticsQuery(
                metric=plan.metric or "order_count",
                dimension=plan.dimension,
                time_grain=plan.time_grain,
                filters=plan.filters,
                sort=plan.sort,
                limit=plan.limit,
            )
            result, cache_hit = analytics_cache.get_or_set(
                _cache_key("analytics", analytics_query),
                lambda: run_analytics(analytics_query),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_copy(
        update={
            "meta": {
                **result.meta,
                "model": model,
                "tool": selected_tool,
                "question": payload.question,
                "cache_hit": cache_hit,
            }
        }
    )
