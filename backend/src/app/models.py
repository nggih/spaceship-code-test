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

    scope: Literal["overall", "category"] = "overall"
    category: str | None = None
    horizon: int = Field(default=3, ge=1, le=6)

    @model_validator(mode="after")
    def require_category(self) -> "ForecastQuery":
        if self.scope == "category" and not self.category:
            raise ValueError("category is required when scope is category")
        if self.scope == "overall":
            self.category = None
        return self


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["analytics", "forecast"]
    metric: Metric | None = None
    dimension: Dimension | None = None
    time_grain: TimeGrain | None = None
    filters: QueryFilters = Field(default_factory=QueryFilters)
    sort: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=50, ge=1, le=200)
    scope: Literal["overall", "category"] | None = None
    category: str | None = None
    horizon: int | None = Field(default=None, ge=1, le=6)

    @model_validator(mode="after")
    def validate_intent_fields(self) -> "AnalysisPlan":
        if self.intent == "analytics" and not self.metric:
            raise ValueError("metric is required for analytics")
        if self.intent == "forecast":
            self.scope = self.scope or "overall"
            self.horizon = self.horizon or 3
            if self.scope == "category" and not self.category:
                raise ValueError("category is required for category forecasts")
        return self


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=500)
    turnstile_token: str | None = Field(default=None, max_length=4096)


class ChartSpec(BaseModel):
    type: ChartType
    title: str
    x_key: str
    y_keys: list[str]
    rows: list[dict[str, Any]]


class Explainability(BaseModel):
    filters: dict[str, Any]
    metric: str
    metric_definition: str
    dimensions: list[str]
    data_anchor: date
    warnings: list[str] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    answer: str
    query_plan: dict[str, Any]
    chart: ChartSpec
    table: dict[str, Any]
    explainability: Explainability
    meta: dict[str, Any] = Field(default_factory=dict)
