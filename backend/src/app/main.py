from __future__ import annotations

import hmac
import os
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response

from .ai import DEFAULT_MODEL, interpret_question
from .analytics import dashboard_payload, run_analytics
from .auth import (
    AUTH_COOKIE_NAME,
    AUTH_SESSION_TTL_SECONDS,
    AuthUser,
    create_credential_session,
    credential_subject,
    password_policy_valid,
    require_user,
)
from .cache import analytics_cache, dashboard_cache, diagnostic_cache, forecast_cache
from .data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS, metadata
from .diagnostic import run_diagnostic
from .forecast import run_forecast
from .history import store_for_request
from .models import (
    AnalyticsQuery,
    AnalyticsResponse,
    AskRequest,
    ClarificationResponse,
    ConversationCreate,
    ConversationUpdate,
    DiagnosticQuery,
    ForecastQuery,
    LoginRequest,
)
from .security import (
    check_login_rate_limit,
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
CurrentUser = Annotated[AuthUser, Depends(require_user)]


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
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PATCH, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-AI-Session, X-Dev-User"
        )
        response.headers["Access-Control-Expose-Headers"] = "X-AI-Session"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if _binding(request, "ENVIRONMENT", "development") == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    response.headers["X-Request-ID"] = request.headers.get(
        "X-Request-ID", str(uuid.uuid4())
    )
    return response


@app.get("/api/health")
async def health(request: Request) -> dict[str, object]:
    configured_username = _binding(request, "USERNAME")
    configured_password = _binding(request, "PASSWORD")
    environment = _binding(request, "ENVIRONMENT", "development")
    session_secret = _binding(request, "AUTH_SESSION_SECRET")
    return {
        "status": "ok",
        "dataset_rows": len(ORDERS),
        "data_min_date": DATA_MIN_DATE,
        "data_max_date": DATA_MAX_DATE,
        "ai_configured": bool(_binding(request, "OPENROUTER_API_KEY")),
        "auth_required": environment == "production",
        "auth_configured": bool(
            configured_username
            and configured_password
            and (session_secret or environment != "production")
        ),
        "password_policy_valid": password_policy_valid(configured_password),
        "history_configured": (
            _runtime_binding(request, "CONVERSATIONS_DB") is not None
            or _binding(request, "HISTORY_DB_PATH") is not None
        ),
        "cache": {
            "analytics": analytics_cache.stats(),
            "forecast": forecast_cache.stats(),
            "diagnostic": diagnostic_cache.stats(),
            "dashboard": dashboard_cache.stats(),
        },
    }


@app.get("/api/metadata")
async def get_metadata(user: CurrentUser) -> dict[str, object]:
    return metadata()


@app.post("/api/dashboard")
async def get_dashboard(query: AnalyticsQuery, user: CurrentUser) -> dict[str, object]:
    try:
        result, _ = dashboard_cache.get_or_set(
            _cache_key("dashboard", query), lambda: dashboard_payload(query)
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analytics", response_model=AnalyticsResponse)
async def analytics(query: AnalyticsQuery, user: CurrentUser) -> AnalyticsResponse:
    try:
        result, hit = analytics_cache.get_or_set(
            _cache_key("analytics", query), lambda: run_analytics(query)
        )
        return result.model_copy(update={"meta": {**result.meta, "cache_hit": hit}})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/forecast", response_model=AnalyticsResponse)
async def forecast(query: ForecastQuery, user: CurrentUser) -> AnalyticsResponse:
    try:
        result, hit = forecast_cache.get_or_set(
            _cache_key("forecast", query), lambda: run_forecast(query)
        )
        return result.model_copy(update={"meta": {**result.meta, "cache_hit": hit}})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/diagnostics", response_model=AnalyticsResponse)
async def diagnostics(query: DiagnosticQuery, user: CurrentUser) -> AnalyticsResponse:
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
    payload: AskRequest, request: Request, response: Response, user: CurrentUser
) -> AnalyticsResponse | ClarificationResponse:
    client_ip = request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )
    turnstile_after_login = (
        _binding(request, "TURNSTILE_AFTER_LOGIN", "false") or "false"
    ).lower() == "true"
    if turnstile_after_login:
        session_secret = _binding(request, "AI_SESSION_SECRET")
        has_session = verify_ai_session(
            request.headers.get("X-AI-Session"),
            client_ip,
            session_secret,
        )
        environment = _binding(request, "ENVIRONMENT", "development")
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
    store = store_for_request(request)
    history = payload.history
    if payload.conversation_id:
        history = await store.context(user, payload.conversation_id)
    await check_rate_limit(
        user.subject, binding=_runtime_binding(request, "AI_RATE_LIMITER")
    )
    plan, model = await interpret_question(
        payload.question,
        history=history,
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
    conversation_id = payload.conversation_id
    if not conversation_id:
        conversation = await store.create(user, payload.question)
        conversation_id = conversation["id"]
    if plan.intent == "clarification":
        result: AnalyticsResponse | ClarificationResponse = ClarificationResponse(
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
                "conversation_id": conversation_id,
            },
        )
        await store.append_exchange(
            user,
            conversation_id,
            payload.question,
            result.message,
            result.model_dump(mode="json"),
        )
        return result
    try:
        if plan.intent == "forecast":
            forecast_query = ForecastQuery(
                scope=plan.scope or "overall",
                category=plan.category,
                sku=plan.sku,
                horizon=plan.horizon or 1,
                method=plan.forecast_method or "auto",
            )
            computed, cache_hit = forecast_cache.get_or_set(
                _cache_key("forecast", forecast_query),
                lambda: run_forecast(forecast_query),
            )
        elif plan.intent == "diagnostic":
            diagnostic_query = DiagnosticQuery(filters=plan.filters)
            computed, cache_hit = diagnostic_cache.get_or_set(
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
            computed, cache_hit = analytics_cache.get_or_set(
                _cache_key("analytics", analytics_query),
                lambda: run_analytics(analytics_query),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = computed.model_copy(
        update={
            "meta": {
                **computed.meta,
                "model": model,
                "tool": selected_tool,
                "question": payload.question,
                "cache_hit": cache_hit,
                "conversation_id": conversation_id,
            }
        }
    )
    await store.append_exchange(
        user,
        conversation_id,
        payload.question,
        result.answer,
        result.model_dump(mode="json"),
    )
    return result


def _identity_payload(request: Request, user: AuthUser) -> dict[str, object]:
    team_domain = (_binding(request, "ACCESS_TEAM_DOMAIN") or "").rstrip("/")
    uses_access = bool(team_domain and not user.subject.startswith("credentials:"))
    return {
        "id": user.subject,
        "email": user.email,
        "name": user.name,
        "logout_url": (
            f"{team_domain}/cdn-cgi/access/logout" if uses_access else None
        ),
    }


@app.post("/api/auth/login")
async def auth_login(
    payload: LoginRequest, request: Request, response: Response
) -> dict[str, object]:
    client_ip = request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )
    await check_login_rate_limit(
        client_ip, binding=_runtime_binding(request, "AI_RATE_LIMITER")
    )
    configured_username = _binding(request, "USERNAME")
    configured_password = _binding(request, "PASSWORD")
    environment = _binding(request, "ENVIRONMENT", "development")
    session_secret = _binding(request, "AUTH_SESSION_SECRET")
    if environment != "production" and not session_secret:
        session_secret = configured_password
    if not configured_username or not configured_password or not session_secret:
        raise HTTPException(status_code=503, detail="Login is not configured.")
    if not password_policy_valid(configured_password):
        raise HTTPException(
            status_code=503,
            detail="Configured login password does not meet the security policy.",
        )
    valid_username = hmac.compare_digest(payload.username, configured_username)
    valid_password = hmac.compare_digest(payload.password, configured_password)
    if not (valid_username and valid_password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_credential_session(configured_username, session_secret)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=environment == "production",
        samesite="lax",
        path="/",
    )
    email = (
        configured_username
        if "@" in configured_username
        else f"{configured_username}@local.account"
    )
    user = AuthUser(
        subject=credential_subject(configured_username),
        email=email,
        name=configured_username,
    )
    return _identity_payload(request, user)


@app.post("/api/auth/logout", status_code=204)
async def auth_logout(
    request: Request, response: Response
) -> Response:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=_binding(request, "ENVIRONMENT", "development") == "production",
        samesite="lax",
        path="/",
    )
    response.status_code = 204
    return response


@app.get("/api/auth/me")
async def auth_me(request: Request, user: CurrentUser) -> dict[str, object]:
    return _identity_payload(request, user)


@app.get("/api/conversations")
async def list_conversations(
    request: Request, user: CurrentUser, limit: int = 50
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 100))
    return {"conversations": await store_for_request(request).list(user, bounded_limit)}


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    payload: ConversationCreate, request: Request, user: CurrentUser
) -> dict[str, object]:
    return await store_for_request(request).create(user, payload.title)


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, request: Request, user: CurrentUser
) -> dict[str, object]:
    return await store_for_request(request).get(user, conversation_id)


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    request: Request,
    user: CurrentUser,
) -> dict[str, object]:
    return await store_for_request(request).rename(user, conversation_id, payload.title)


@app.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str, request: Request, user: CurrentUser
) -> Response:
    await store_for_request(request).delete(user, conversation_id)
    return Response(status_code=204)
