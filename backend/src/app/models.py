from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Metric = Literal[
    "order_count",
    "delivered_orders",
    "delayed_orders",
    "on_time_rate",
    "average_delivery_time",
    "demand",
    "revenue",
    "delay_rate",
]
Dimension = Literal[
    "day",
    "week",
    "month",
    "carrier",
    "destination",
    "origin",
    "region",
    "warehouse",
    "category",
    "sku",
    "status",
    "promo",
]
TimeGrain = Literal["day", "week", "month"]
ChartType = Literal["line", "bar", "horizontal_bar", "pie", "table"]


class QueryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None
    carriers: list[str] = Field(default_factory=list, max_length=10)
    regions: list[str] = Field(default_factory=list, max_length=10)
    warehouses: list[str] = Field(default_factory=list, max_length=10)
    categories: list[str] = Field(default_factory=list, max_length=10)
    skus: list[str] = Field(default_factory=list, max_length=20)
    statuses: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_dates(self) -> "QueryFilters":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class AnalyticsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Metric = "order_count"
    dimension: Dimension | None = None
    time_grain: TimeGrain | None = None
    filters: QueryFilters = Field(default_factory=QueryFilters)
    sort: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def normalize_time_dimension(self) -> "AnalyticsQuery":
        if self.dimension in {"day", "week", "month"}:
            self.time_grain = self.dimension
        return self


class ForecastQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["overall", "category", "sku"] = "overall"
    category: str | None = None
    sku: str | None = None
    horizon: int = Field(default=3, ge=1, le=6)

    @model_validator(mode="after")
    def require_category(self) -> "ForecastQuery":
        if self.scope == "category" and not self.category:
            raise ValueError("category is required when scope is category")
        if self.scope == "sku" and not self.sku:
            raise ValueError("sku is required when scope is sku")
        if self.scope == "overall":
            self.category = None
            self.sku = None
        elif self.scope == "category":
            self.sku = None
        else:
            self.category = None
        return self


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["analytics", "diagnostic", "forecast", "clarification"] = Field(
        description="Selects exactly one computation path; never contains an answer."
    )
    metric: Metric | None = Field(
        default=None, description="Approved metric required only for analytics."
    )
    dimension: Dimension | None = Field(
        default=None,
        description="Single approved grouping; time dimensions must match time_grain.",
    )
    time_grain: TimeGrain | None = Field(
        default=None, description="Day, week, or month only for time-series analytics."
    )
    filters: QueryFilters = Field(default_factory=QueryFilters)
    sort: Literal["asc", "desc"] = Field(
        default="asc", description="Ascending for time series; ranking direction otherwise."
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="50 unless the user explicitly requests a bounded top/bottom N.",
    )
    scope: Literal["overall", "category", "sku"] | None = Field(
        default=None, description="Required only for forecasting."
    )
    category: str | None = None
    sku: str | None = None
    horizon: int | None = Field(default=None, ge=1, le=6)
    clarification_question: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_intent_fields(self) -> "AnalysisPlan":
        if self.intent == "analytics" and not self.metric:
            raise ValueError("metric is required for analytics")
        if self.intent == "analytics":
            time_dimensions = {"day", "week", "month"}
            if self.dimension in time_dimensions and self.time_grain != self.dimension:
                raise ValueError("time dimension and time_grain must match")
            if (
                self.dimension not in time_dimensions
                and self.dimension is not None
                and self.time_grain is not None
            ):
                raise ValueError(
                    "categorical dimension and time_grain cannot both be populated"
                )
            if self.dimension is None and self.time_grain is not None:
                raise ValueError("time_grain requires the matching time dimension")
        if self.intent == "forecast":
            self.scope = self.scope or "overall"
            self.horizon = self.horizon or 3
            if self.scope == "category" and not self.category:
                raise ValueError("category is required for category forecasts")
            if self.scope == "sku" and not self.sku:
                raise ValueError("sku is required for SKU forecasts")
        if self.intent == "clarification" and not self.clarification_question:
            raise ValueError("clarification_question is required for ambiguous requests")
        return self


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=500)
    turnstile_token: str | None = Field(default=None, max_length=4096)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_history_order(self) -> "AskRequest":
        for index, turn in enumerate(self.history):
            expected = "user" if index % 2 == 0 else "assistant"
            if turn.role != expected:
                raise ValueError(
                    "history must contain complete alternating user/assistant turns"
                )
        if self.history and self.history[-1].role != "assistant":
            raise ValueError("history must end with an assistant turn")
        return self


class ChartSpec(BaseModel):
    type: ChartType
    title: str
    x_key: str
    y_keys: list[str]
    rows: list[dict[str, Any]]
    query_plan: dict[str, Any] | None = None
    explainability: dict[str, Any] | None = None


class Explainability(BaseModel):
    filters: dict[str, Any]
    metric: str
    metric_definition: str
    dimensions: list[str]
    data_anchor: date
    warnings: list[str] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    kind: Literal["result"] = "result"
    answer: str
    query_plan: dict[str, Any]
    chart: ChartSpec
    table: dict[str, Any]
    explainability: Explainability
    meta: dict[str, Any] = Field(default_factory=dict)


class ClarificationResponse(BaseModel):
    kind: Literal["clarification"] = "clarification"
    message: str
    suggestions: list[str] = Field(default_factory=list)
    query_plan: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)


class DiagnosticQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: QueryFilters = Field(default_factory=QueryFilters)
    minimum_sample: int = Field(default=5, ge=3, le=50)
    limit: int = Field(default=10, ge=1, le=25)
