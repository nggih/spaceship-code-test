from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics import calculate_metric, filter_orders, run_analytics
from app.data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS
from app.diagnostic import run_diagnostic
from app.embedded_data import CSV_DATA
from app.forecast import run_forecast
from app.main import app
from app.models import (
    AnalysisPlan,
    AnalyticsQuery,
    DiagnosticQuery,
    ForecastQuery,
    QueryFilters,
)

client = TestClient(app)


def test_dataset_invariants():
    assert len(ORDERS) == 400
    assert DATA_MIN_DATE == date(2025, 1, 1)
    assert DATA_MAX_DATE == date(2025, 12, 30)
    assert sum(row.delivery_date is None for row in ORDERS) == 30


def test_worker_embedded_dataset_matches_canonical_csv():
    canonical = Path(__file__).resolve().parents[2] / "data" / "mock_logistics_data.csv"
    assert canonical.read_text(encoding="utf-8") == CSV_DATA


def test_required_kpis():
    assert calculate_metric("order_count", ORDERS) == 400
    assert calculate_metric("delivered_orders", ORDERS) == 304
    assert calculate_metric("delayed_orders", ORDERS) == 55
    assert calculate_metric("on_time_rate", ORDERS) == pytest.approx(84.68)
    assert calculate_metric("average_delivery_time", ORDERS) > 0


def test_combined_filters():
    query = AnalyticsQuery(
        filters=QueryFilters(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            carriers=["DHL"],
            regions=["EU"],
        )
    )
    rows = filter_orders(query)
    assert rows
    assert all(row.carrier == "DHL" for row in rows)
    assert all(row.region == "EU" for row in rows)
    assert all(date(2025, 1, 1) <= row.order_date <= date(2025, 3, 31) for row in rows)


def test_month_grouping_zero_fills_requested_range():
    result = run_analytics(
        AnalyticsQuery(
            metric="order_count",
            dimension="month",
            filters=QueryFilters(
                start_date=date(2025, 1, 1), end_date=date(2025, 12, 30)
            ),
        )
    )
    assert len(result.chart.rows) == 12
    assert result.chart.rows[0]["label"] == "2025-01-01"
    assert result.chart.rows[-1]["label"] == "2025-12-01"
    assert sum(row["value"] for row in result.chart.rows) == 400


def test_carrier_delay_rate_ranking():
    result = run_analytics(
        AnalyticsQuery(metric="delay_rate", dimension="carrier", sort="desc")
    )
    values = [row["value"] for row in result.chart.rows]
    assert values == sorted(values, reverse=True)
    assert "highest delay rate among carrier groups" in result.answer.lower()
    assert "completed orders" in result.answer.lower()


def test_business_answer_names_metric_period_and_grain():
    result = run_analytics(
        AnalyticsQuery(
            metric="delayed_orders",
            dimension="week",
            filters=QueryFilters(
                start_date=date(2025, 9, 30),
                end_date=date(2025, 12, 30),
                statuses=["delayed"],
            ),
        )
    )
    assert result.answer.startswith(
        "There were 10 delayed orders from 30 Sep–30 Dec 2025."
    )
    assert "breaks this into 14 weeks" in result.answer


def test_business_answer_recognizes_full_calendar_month():
    result = run_analytics(
        AnalyticsQuery(
            metric="delayed_orders",
            filters=QueryFilters(
                start_date=date(2025, 11, 1),
                end_date=date(2025, 11, 30),
                statuses=["delayed"],
            ),
        )
    )
    assert result.answer == "There were 4 delayed orders in November 2025."


def test_forecast_overall_and_category():
    overall = run_forecast(ForecastQuery(scope="overall", horizon=4))
    category = run_forecast(
        ForecastQuery(scope="category", category="PAPER", horizon=2)
    )
    assert len(overall.table["rows"]) == 4
    assert len(category.table["rows"]) == 2
    assert all(row["forecast"] >= 0 for row in overall.table["rows"])
    assert (
        overall.meta["inventory_recommendation"] >= overall.table["rows"][0]["forecast"]
    )
    assert overall.meta["method"] in {
        "moving_average_3",
        "linear_trend",
        "exponential_smoothing",
        "naive",
    }


def test_forecast_auto_selects_lowest_mae_without_duplicate_boundary_month():
    result = run_forecast(ForecastQuery(scope="overall", horizon=6, method="auto"))
    scores = result.meta["candidate_scores"]
    selected = next(score for score in scores if score["selected"])
    assert selected["mae"] == min(score["mae"] for score in scores)
    assert selected["method"] == result.meta["method"]
    assert result.meta["validation_periods"] == 9

    labels = [row["label"] for row in result.chart.rows]
    assert len(labels) == len(set(labels))
    boundary = result.chart.rows[11]
    assert boundary["label"] == "2025-12"
    assert boundary["historical"] == boundary["forecast"]


@pytest.mark.parametrize(
    "method",
    [
        "moving_average_3",
        "linear_trend",
        "exponential_smoothing",
        "naive",
    ],
)
def test_forecast_supports_each_approved_method(method):
    result = run_forecast(ForecastQuery(scope="overall", horizon=2, method=method))
    assert result.meta["method"] == method
    assert result.meta["requested_method"] == method
    assert len(result.table["rows"]) == 2
    assert all(row["forecast"] >= 0 for row in result.table["rows"])


def test_sparse_sku_forecast_is_supported_with_low_confidence():
    sku = ORDERS[0].sku
    result = run_forecast(ForecastQuery(scope="sku", sku=sku, horizon=2))
    assert len(result.table["rows"]) == 2
    assert result.meta["confidence"] == "low"
    assert result.meta["safety_stock_percent"] == 30
    assert any(
        "Low-confidence SKU forecast" in warning
        for warning in result.explainability.warnings
    )


def test_unknown_forecast_category():
    with pytest.raises(ValueError, match="Unknown category"):
        run_forecast(ForecastQuery(scope="category", category="NOT_REAL", horizon=2))


def test_forecast_horizon_bounds_are_rejected():
    for horizon in (0, 7):
        response = client.post(
            "/api/forecast",
            json={"scope": "overall", "horizon": horizon, "method": "auto"},
        )
        assert response.status_code == 422


def test_forecast_plan_rejects_unsupported_segmentation_and_normalizes_duplicate_sku():
    with pytest.raises(ValueError, match="forecast plans cannot contain"):
        AnalysisPlan(
            intent="forecast",
            scope="overall",
            horizon=1,
            forecast_method="auto",
            filters=QueryFilters(regions=["EU"]),
        )

    plan = AnalysisPlan(
        intent="forecast",
        scope="sku",
        sku=ORDERS[0].sku,
        horizon=2,
        forecast_method="auto",
        filters=QueryFilters(skus=[ORDERS[0].sku]),
    )
    assert plan.filters.skus == []


def test_diagnostic_ranks_delay_associations_and_warns_about_causality():
    result = run_diagnostic(DiagnosticQuery(minimum_sample=5, limit=6))
    assert result.chart.type == "horizontal_bar"
    assert result.table["rows"]
    lifts = [row["lift_vs_overall"] for row in result.table["rows"]]
    assert lifts == sorted(lifts, reverse=True)
    assert any(
        "do not prove causation" in warning
        for warning in result.explainability.warnings
    )
    assert result.chart.query_plan == result.query_plan


def test_api_validation_and_health():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["dataset_rows"] == 400

    invalid_metric = client.post(
        "/api/analytics", json={"metric": "raw_sql", "limit": 10}
    )
    assert invalid_metric.status_code == 422

    invalid_dates = client.post(
        "/api/analytics",
        json={
            "metric": "order_count",
            "filters": {"start_date": "2025-12-01", "end_date": "2025-01-01"},
        },
    )
    assert invalid_dates.status_code == 422

    unknown_filter = client.post(
        "/api/analytics",
        json={"metric": "order_count", "filters": {"carriers": ["NOT_A_CARRIER"]}},
    )
    assert unknown_filter.status_code == 400
    assert "Unknown carriers" in unknown_filter.json()["detail"]

    invalid_history = client.post(
        "/api/ask",
        json={
            "question": "Now compare by region",
            "history": [{"role": "assistant", "content": "Previous answer"}],
        },
    )
    assert invalid_history.status_code == 422


def test_dashboard_payload_endpoint():
    response = client.post("/api/dashboard", json={"metric": "order_count"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["order_count"] == 400
    assert set(payload["charts"]) == {"volume", "status", "carriers"}
    assert payload["charts"]["volume"]["query_plan"]
    assert payload["charts"]["carriers"]["explainability"]
    assert payload["table"]["total"] == 400
    assert len(payload["table"]["rows"]) == 400
    assert set(payload["table"]["rows"][0]) == {
        "client_id",
        "order_id",
        "order_date",
        "delivery_date",
        "carrier",
        "origin_city",
        "destination_city",
        "status",
        "sku",
        "product_category",
        "quantity",
        "unit_price_usd",
        "order_value_usd",
        "is_promo",
        "promo_discount_pct",
        "region",
        "warehouse",
    }


def test_analytics_response_cache_reports_hit():
    payload = {"metric": "demand", "dimension": "category", "sort": "desc"}
    first = client.post("/api/analytics", json=payload)
    second = client.post("/api/analytics", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["meta"]["cache_hit"] is True


def test_diagnostics_endpoint():
    response = client.post("/api/diagnostics", json={"minimum_sample": 5, "limit": 5})
    assert response.status_code == 200
    assert len(response.json()["table"]["rows"]) == 5
