from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Callable, Iterable

from .data import DATA_MAX_DATE, Order, ORDERS
from .models import AnalyticsQuery, AnalyticsResponse, ChartSpec, Explainability

METRIC_DEFINITIONS = {
    "order_count": "Distinct order IDs.",
    "delivered_orders": "Orders whose status is delivered.",
    "delayed_orders": "Orders whose status is delayed.",
    "on_time_rate": "Delivered orders divided by delivered plus delayed orders.",
    "average_delivery_time": "Average calendar days from order to delivery for delivered or delayed orders.",
    "demand": "Sum of ordered quantity.",
    "revenue": "Sum of order value in USD.",
    "delay_rate": "Delayed orders divided by delivered plus delayed orders.",
}

DIMENSION_FIELDS: dict[str, Callable[[Order], str]] = {
    "carrier": lambda row: row.carrier,
    "destination": lambda row: row.destination_city,
    "origin": lambda row: row.origin_city,
    "region": lambda row: row.region,
    "warehouse": lambda row: row.warehouse,
    "category": lambda row: row.product_category,
    "sku": lambda row: row.sku,
    "status": lambda row: row.status,
    "promo": lambda row: "Promo" if row.is_promo else "No promo",
}


def filter_orders(query: AnalyticsQuery, rows: Iterable[Order] = ORDERS) -> list[Order]:
    filters = query.filters
    result = []
    for row in rows:
        if filters.start_date and row.order_date < filters.start_date:
            continue
        if filters.end_date and row.order_date > filters.end_date:
            continue
        if filters.carriers and row.carrier not in filters.carriers:
            continue
        if filters.regions and row.region not in filters.regions:
            continue
        if filters.warehouses and row.warehouse not in filters.warehouses:
            continue
        if filters.categories and row.product_category not in filters.categories:
            continue
        if filters.skus and row.sku not in filters.skus:
            continue
        if filters.statuses and row.status not in filters.statuses:
            continue
        result.append(row)
    return result


def calculate_metric(metric: str, rows: Iterable[Order]) -> float:
    items = list(rows)
    if metric == "order_count":
        return float(len({row.order_id for row in items}))
    if metric == "delivered_orders":
        return float(sum(row.status == "delivered" for row in items))
    if metric == "delayed_orders":
        return float(sum(row.status == "delayed" for row in items))
    if metric == "demand":
        return float(sum(row.quantity for row in items))
    if metric == "revenue":
        return round(sum(row.order_value_usd for row in items), 2)

    completed = [row for row in items if row.status in {"delivered", "delayed"}]
    delivered = sum(row.status == "delivered" for row in completed)
    delayed = sum(row.status == "delayed" for row in completed)
    denominator = delivered + delayed
    if metric == "on_time_rate":
        return round((delivered / denominator * 100) if denominator else 0, 2)
    if metric == "delay_rate":
        return round((delayed / denominator * 100) if denominator else 0, 2)
    if metric == "average_delivery_time":
        durations = [
            (row.delivery_date - row.order_date).days
            for row in completed
            if row.delivery_date
        ]
        return round(sum(durations) / len(durations), 2) if durations else 0
    raise ValueError(f"Unsupported metric: {metric}")


def _time_key(value: date, grain: str) -> str:
    if grain == "day":
        return value.isoformat()
    if grain == "week":
        monday = value - timedelta(days=value.weekday())
        return monday.isoformat()
    return value.replace(day=1).isoformat()


def _next_period(value: date, grain: str) -> date:
    if grain == "day":
        return value + timedelta(days=1)
    if grain == "week":
        return value + timedelta(days=7)
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def _time_groups(rows: list[Order], grain: str, query: AnalyticsQuery) -> list[tuple[str, list[Order]]]:
    grouped: dict[str, list[Order]] = defaultdict(list)
    for row in rows:
        grouped[_time_key(row.order_date, grain)].append(row)
    if not rows and not (query.filters.start_date and query.filters.end_date):
        return []
    start = query.filters.start_date or min((row.order_date for row in rows), default=DATA_MAX_DATE)
    end = query.filters.end_date or max((row.order_date for row in rows), default=DATA_MAX_DATE)
    if grain == "week":
        start -= timedelta(days=start.weekday())
    elif grain == "month":
        start = start.replace(day=1)
    output = []
    cursor = start
    while cursor <= end:
        key = _time_key(cursor, grain)
        output.append((key, grouped.get(key, [])))
        cursor = _next_period(cursor, grain)
    return output


def _format_value(metric: str, value: float) -> str:
    if metric in {"on_time_rate", "delay_rate"}:
        return f"{value:.1f}%"
    if metric == "average_delivery_time":
        return f"{value:.1f} days"
    if metric == "revenue":
        return f"${value:,.2f}"
    return f"{int(value):,}"


def run_analytics(query: AnalyticsQuery) -> AnalyticsResponse:
    filtered = filter_orders(query)
    dimension = query.time_grain or query.dimension
    if dimension in {"day", "week", "month"}:
        groups = _time_groups(filtered, dimension, query)
    elif dimension:
        bucket: dict[str, list[Order]] = defaultdict(list)
        getter = DIMENSION_FIELDS[dimension]
        for row in filtered:
            bucket[getter(row)].append(row)
        groups = list(bucket.items())
    else:
        groups = [("All orders", filtered)]

    rows = [
        {"label": label, "value": calculate_metric(query.metric, group)}
        for label, group in groups
    ]
    if dimension not in {"day", "week", "month"}:
        rows.sort(key=lambda row: row["value"], reverse=query.sort == "desc")
    rows = rows[: query.limit]
    total = calculate_metric(query.metric, filtered)

    chart_type = "table"
    if dimension in {"day", "week", "month"}:
        chart_type = "line"
    elif dimension == "status":
        chart_type = "pie"
    elif dimension:
        chart_type = "horizontal_bar" if len(rows) > 5 else "bar"

    answer = f"{_format_value(query.metric, total)} across {len(filtered):,} matching orders."
    if dimension and rows and query.sort == "desc":
        answer += f" The leading {dimension} is {rows[0]['label']} at {_format_value(query.metric, rows[0]['value'])}."

    filter_dump = query.filters.model_dump(mode="json", exclude_none=True)
    filter_dump = {key: value for key, value in filter_dump.items() if value not in ([], None)}
    warnings = [
        "“Late” means status=delayed because the dataset has no promised delivery date."
    ]
    response = AnalyticsResponse(
        answer=answer,
        query_plan=query.model_dump(mode="json"),
        chart=ChartSpec(
            type=chart_type,
            title=f"{query.metric.replace('_', ' ').title()}"
            + (f" by {dimension}" if dimension else ""),
            x_key="label",
            y_keys=["value"],
            rows=rows,
        ),
        table={"columns": ["label", "value"], "rows": rows},
        explainability=Explainability(
            filters=filter_dump,
            metric=query.metric,
            metric_definition=METRIC_DEFINITIONS[query.metric],
            dimensions=[dimension] if dimension else [],
            data_anchor=DATA_MAX_DATE,
            warnings=warnings,
        ),
    )
    response.chart.query_plan = response.query_plan
    response.chart.explainability = response.explainability.model_dump(mode="json")
    return response


def dashboard_payload(query: AnalyticsQuery) -> dict[str, object]:
    filtered = filter_orders(query)
    kpis = {
        metric: calculate_metric(metric, filtered)
        for metric in (
            "order_count",
            "delivered_orders",
            "delayed_orders",
            "on_time_rate",
            "average_delivery_time",
        )
    }
    base_filters = query.filters
    volume = run_analytics(
        AnalyticsQuery(metric="order_count", dimension="month", filters=base_filters)
    ).chart
    status = run_analytics(
        AnalyticsQuery(metric="order_count", dimension="status", filters=base_filters)
    ).chart
    carriers = run_analytics(
        AnalyticsQuery(
            metric="delay_rate",
            dimension="carrier",
            filters=base_filters,
            sort="desc",
        )
    ).chart
    detail_rows = [
        {
            "order_id": row.order_id,
            "order_date": row.order_date.isoformat(),
            "carrier": row.carrier,
            "destination": row.destination_city,
            "status": row.status,
            "category": row.product_category,
            "quantity": row.quantity,
            "value": row.order_value_usd,
        }
        for row in filtered[:100]
    ]
    return {
        "kpis": kpis,
        "charts": {"volume": volume, "status": status, "carriers": carriers},
        "table": {"rows": detail_rows, "total": len(filtered)},
        "filters": base_filters.model_dump(mode="json", exclude_none=True),
        "data_anchor": DATA_MAX_DATE,
    }
