from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from statistics import mean

from .data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS
from .models import (
    AnalyticsResponse,
    ChartSpec,
    Explainability,
    ForecastMethod,
    ForecastQuery,
)

ForecastFunction = Callable[[list[float], int], list[float]]

METHOD_LABELS: dict[ForecastMethod, str] = {
    "auto": "Automatic backtest selection",
    "moving_average_3": "3-month moving average",
    "linear_trend": "Ordinary least-squares linear trend",
    "exponential_smoothing": "Simple exponential smoothing",
    "naive": "Last-observation baseline",
}


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


def _moving_average(values: list[float], horizon: int) -> list[float]:
    working = list(values)
    output = []
    for _ in range(horizon):
        prediction = mean(working[-min(3, len(working)) :])
        output.append(prediction)
        working.append(prediction)
    return output


def _linear_trend(values: list[float], horizon: int) -> list[float]:
    intercept, slope = _linear_regression(values)
    return [intercept + slope * (len(values) + offset) for offset in range(horizon)]


def _exponential_smoothing(
    values: list[float], horizon: int, alpha: float = 0.3
) -> list[float]:
    level = values[0]
    for value in values[1:]:
        level = alpha * value + (1 - alpha) * level
    return [level] * horizon


def _naive(values: list[float], horizon: int) -> list[float]:
    return [values[-1]] * horizon


FORECASTERS: dict[ForecastMethod, ForecastFunction] = {
    "moving_average_3": _moving_average,
    "exponential_smoothing": _exponential_smoothing,
    "naive": _naive,
    "linear_trend": _linear_trend,
}


def _rolling_mae(values: list[float], method: ForecastMethod) -> float:
    errors = []
    for cutoff in range(3, len(values)):
        prediction = FORECASTERS[method](values[:cutoff], 1)[0]
        errors.append(abs(values[cutoff] - max(0, prediction)))
    return mean(errors) if errors else math.inf


def _select_method(
    values: list[float], requested: ForecastMethod
) -> tuple[ForecastMethod, list[dict[str, object]]]:
    scores_by_method = {method: _rolling_mae(values, method) for method in FORECASTERS}
    selected = (
        min(scores_by_method, key=scores_by_method.__getitem__)
        if requested == "auto"
        else requested
    )
    scores = [
        {
            "method": method,
            "label": METHOD_LABELS[method],
            "mae": round(score, 2),
            "selected": method == selected,
        }
        for method, score in scores_by_method.items()
    ]
    return selected, scores


def _history_months() -> list[date]:
    start = DATA_MIN_DATE.replace(day=1)
    end = DATA_MAX_DATE.replace(day=1)
    months = []
    cursor = start
    while cursor <= end:
        months.append(cursor)
        cursor = _month_add(cursor, 1)
    return months


def run_forecast(query: ForecastQuery) -> AnalyticsResponse:
    category = query.category.upper() if query.category else None
    sku = query.sku.upper() if query.sku else None
    available_categories = {row.product_category for row in ORDERS}
    available_skus = {row.sku for row in ORDERS}
    if category and category not in available_categories:
        raise ValueError(f"Unknown category: {query.category}")
    if sku and sku not in available_skus:
        raise ValueError(f"Unknown SKU: {query.sku}")

    selected_orders = [
        row
        for row in ORDERS
        if (not category or row.product_category == category)
        and (not sku or row.sku == sku)
    ]
    monthly: dict[str, int] = defaultdict(int)
    for row in selected_orders:
        monthly[row.order_date.strftime("%Y-%m")] += row.quantity

    history_dates = _history_months()
    history = [float(monthly[value.strftime("%Y-%m")]) for value in history_dates]
    selected_method, validation_scores = _select_method(history, query.method)
    raw_projections = FORECASTERS[selected_method](history, query.horizon)
    projections = [max(0, math.ceil(value)) for value in raw_projections]

    rows = [
        {
            "label": value.strftime("%Y-%m"),
            "historical": int(amount),
            "forecast": None,
        }
        for value, amount in zip(history_dates, history)
    ]
    # Give both series one shared boundary point without duplicating the month label.
    rows[-1]["forecast"] = rows[-1]["historical"]
    forecast_start = _month_add(history_dates[-1], 1)
    rows.extend(
        {
            "label": _month_add(forecast_start, offset).strftime("%Y-%m"),
            "historical": None,
            "forecast": value,
        }
        for offset, value in enumerate(projections)
    )

    sparse_sku = query.scope == "sku" and len(selected_orders) < 6
    safety_stock = 30 if sparse_sku else 15
    recommendation = math.ceil(projections[0] * (1 + safety_stock / 100))
    label = sku or category or "overall"
    unit_label = "unit" if projections[0] == 1 else "units"
    answer = (
        f"Forecast demand for {label} is {projections[0]:,} {unit_label} next month "
        f"using {METHOD_LABELS[selected_method].lower()}. "
        f"Plan approximately {recommendation:,} units including "
        f"{safety_stock}% safety stock."
    )

    selected_score = next(
        score for score in validation_scores if score["method"] == selected_method
    )
    validation_periods = max(0, len(history) - 3)
    warnings = [
        (
            f"Illustrative forecast based on only {len(history)} months and "
            f"{len(ORDERS)} source orders."
        ),
        (
            f"Method comparison uses {validation_periods} expanding-window, "
            "one-step validation periods; MAE is descriptive, not a confidence interval."
        ),
    ]
    if sparse_sku:
        warnings.append(
            f"Low-confidence SKU forecast: {label} has only "
            f"{len(selected_orders)} source order(s); zeros dominate the monthly series, "
            "so use this as a conservative planning signal."
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
                    "month": _month_add(forecast_start, offset).strftime("%Y-%m"),
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
                "requested_method": query.method,
                "selected_method": selected_method,
            },
            metric="demand",
            metric_definition=(
                "Monthly sum of quantity forecast with "
                f"{METHOD_LABELS[selected_method].lower()}. Automatic mode compares "
                "approved methods using expanding-window one-step mean absolute error."
            ),
            dimensions=["month", query.scope],
            data_anchor=DATA_MAX_DATE,
            warnings=warnings,
        ),
        meta={
            "method": selected_method,
            "method_label": METHOD_LABELS[selected_method],
            "requested_method": query.method,
            "validation_mae": selected_score["mae"],
            "validation_periods": validation_periods,
            "candidate_scores": validation_scores,
            "inventory_recommendation": recommendation,
            "safety_stock_percent": safety_stock,
            "supporting_orders": len(selected_orders),
            "confidence": "low" if sparse_sku else "illustrative",
        },
    )
    response.chart.query_plan = response.query_plan
    response.chart.explainability = response.explainability.model_dump(mode="json")
    return response
