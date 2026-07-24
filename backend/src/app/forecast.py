from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from .data import DATA_MAX_DATE, ORDERS
from .models import AnalyticsResponse, ChartSpec, Explainability, ForecastQuery


def _month_add(value: date, months: int) -> date:
    offset = value.month - 1 + months
    return date(value.year + offset // 12, offset % 12 + 1, 1)


def _linear_regression(values: list[float]) -> tuple[float, float]:
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denominator
        if denominator
        else 0
    )
    return mean_y - slope * mean_x, slope


def run_forecast(query: ForecastQuery) -> AnalyticsResponse:
    category = query.category.upper() if query.category else None
    sku = query.sku.upper() if query.sku else None
    available_categories = {row.product_category for row in ORDERS}
    available_skus = {row.sku for row in ORDERS}
    if category and category not in available_categories:
        raise ValueError(f"Unknown category: {query.category}")
    if sku and sku not in available_skus:
        raise ValueError(f"Unknown SKU: {query.sku}")
    selected = [
        row
        for row in ORDERS
        if (not category or row.product_category == category)
        and (not sku or row.sku == sku)
    ]
    start = date(min(row.order_date.year for row in ORDERS), 1, 1)
    monthly: dict[str, int] = defaultdict(int)
    for row in selected:
        monthly[row.order_date.strftime("%Y-%m")] += row.quantity
    history_dates = [_month_add(start, index) for index in range(12)]
    history = [float(monthly[value.strftime("%Y-%m")]) for value in history_dates]
    intercept, slope = _linear_regression(history)
    projections = [
        max(0, math.ceil(intercept + slope * (12 + offset)))
        for offset in range(query.horizon)
    ]
    rows = [
        {"label": value.strftime("%Y-%m"), "historical": int(amount), "forecast": None}
        for value, amount in zip(history_dates, history)
    ]
    last_history = rows[-1]["historical"]
    rows.append(
        {
            "label": history_dates[-1].strftime("%Y-%m"),
            "historical": None,
            "forecast": last_history,
        }
    )
    rows.extend(
        {
            "label": _month_add(start, 12 + offset).strftime("%Y-%m"),
            "historical": None,
            "forecast": value,
        }
        for offset, value in enumerate(projections)
    )
    sparse_sku = query.scope == "sku" and len(selected) < 6
    safety_stock = 30 if sparse_sku else 15
    recommendation = math.ceil(projections[0] * (1 + safety_stock / 100))
    label = sku or category or "overall"
    answer = (
        f"Forecast demand for {label} is {projections[0]:,} units next month. "
        f"Plan approximately {recommendation:,} units including {safety_stock}% safety stock."
    )
    warnings = [
        "Illustrative forecast based on only 12 months and 400 source orders.",
    ]
    if sparse_sku:
        warnings.append(
            f"Low-confidence SKU forecast: {label} has only {len(selected)} source order(s); "
            "zeros dominate the monthly series, so use this as a conservative planning signal."
        )
    response = AnalyticsResponse(
        answer=answer,
        query_plan=query.model_dump(mode="json"),
        chart=ChartSpec(
            type="line",
            title=f"{label.title()} demand forecast",
            x_key="label",
            y_keys=["historical", "forecast"],
            rows=rows,
        ),
        table={
            "columns": ["month", "forecast"],
            "rows": [
                {
                    "month": _month_add(start, 12 + offset).strftime("%Y-%m"),
                    "forecast": value,
                }
                for offset, value in enumerate(projections)
            ],
        },
        explainability=Explainability(
            filters={
                "scope": query.scope,
                "category": category,
                "sku": sku,
                "horizon": query.horizon,
            },
            metric="demand",
            metric_definition="Monthly sum of quantity forecast with an ordinary least-squares linear trend.",
            dimensions=["month", query.scope],
            data_anchor=DATA_MAX_DATE,
            warnings=warnings,
        ),
        meta={
            "method": "ordinary_least_squares_linear_trend",
            "slope": round(slope, 4),
            "inventory_recommendation": recommendation,
            "safety_stock_percent": safety_stock,
            "supporting_orders": len(selected),
            "confidence": "low" if sparse_sku else "illustrative",
        },
    )
    response.chart.query_plan = response.query_plan
    response.chart.explainability = response.explainability.model_dump(mode="json")
    return response
