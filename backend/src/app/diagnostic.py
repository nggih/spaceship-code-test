from __future__ import annotations

from collections import defaultdict

from .analytics import DIMENSION_FIELDS, calculate_metric, filter_orders
from .data import DATA_MAX_DATE, Order
from .models import (
    AnalyticsQuery,
    AnalyticsResponse,
    ChartSpec,
    DiagnosticQuery,
    Explainability,
)

DIAGNOSTIC_DIMENSIONS = ("carrier", "region", "warehouse", "category", "promo")


def run_diagnostic(query: DiagnosticQuery) -> AnalyticsResponse:
    analytics_query = AnalyticsQuery(filters=query.filters)
    filtered = filter_orders(analytics_query)
    overall_rate = calculate_metric("delay_rate", filtered)
    candidates: list[dict[str, object]] = []
    for dimension in DIAGNOSTIC_DIMENSIONS:
        groups: dict[str, list[Order]] = defaultdict(list)
        getter = DIMENSION_FIELDS[dimension]
        for row in filtered:
            groups[getter(row)].append(row)
        for segment, rows in groups.items():
            completed = sum(row.status in {"delivered", "delayed"} for row in rows)
            if completed < query.minimum_sample:
                continue
            rate = calculate_metric("delay_rate", rows)
            candidates.append(
                {
                    "label": f"{dimension.title()}: {segment}",
                    "dimension": dimension,
                    "segment": segment,
                    "completed_orders": completed,
                    "delayed_orders": int(calculate_metric("delayed_orders", rows)),
                    "delay_rate": rate,
                    "lift_vs_overall": round(rate - overall_rate, 2),
                }
            )
    candidates.sort(
        key=lambda row: (float(row["lift_vs_overall"]), int(row["completed_orders"])),
        reverse=True,
    )
    rows = candidates[: query.limit]
    leader = rows[0] if rows else None
    answer = (
        f"The strongest observed delay association is {leader['label']} at "
        f"{leader['delay_rate']:.1f}%—{leader['lift_vs_overall']:+.1f} percentage "
        f"points versus the {overall_rate:.1f}% baseline."
        if leader
        else "No segment has enough completed orders for a reliable diagnostic comparison."
    )
    plan = {
        "intent": "diagnostic",
        "metric": "delay_rate",
        "dimensions_evaluated": list(DIAGNOSTIC_DIMENSIONS),
        **query.model_dump(mode="json"),
    }
    explainability = Explainability(
        filters=query.filters.model_dump(mode="json", exclude_none=True),
        metric="delay_rate_lift",
        metric_definition=(
            "Segment delay rate minus the overall delay rate, evaluated only for "
            f"segments with at least {query.minimum_sample} completed orders."
        ),
        dimensions=list(DIAGNOSTIC_DIMENSIONS),
        data_anchor=DATA_MAX_DATE,
        warnings=[
            "Associations identify where delays concentrate; they do not prove causation.",
            "Late means status=delayed because promised delivery dates are unavailable.",
        ],
    )
    response = AnalyticsResponse(
        answer=answer,
        query_plan=plan,
        chart=ChartSpec(
            type="horizontal_bar",
            title="Segments associated with elevated delay rates",
            x_key="label",
            y_keys=["delay_rate"],
            rows=rows,
        ),
        table={
            "columns": [
                "dimension",
                "segment",
                "completed_orders",
                "delayed_orders",
                "delay_rate",
                "lift_vs_overall",
            ],
            "rows": rows,
        },
        explainability=explainability,
        meta={"baseline_delay_rate": overall_rate, "analysis_type": "association"},
    )
    response.chart.query_plan = plan
    response.chart.explainability = explainability.model_dump(mode="json")
    return response

