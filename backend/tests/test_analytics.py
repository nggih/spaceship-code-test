from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics import calculate_metric, filter_orders, run_analytics
from app.data import DATA_MAX_DATE, DATA_MIN_DATE, ORDERS
from app.embedded_data import CSV_DATA
from app.forecast import run_forecast
from app.main import app
from app.models import AnalyticsQuery, ForecastQuery, QueryFilters

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
        AnalyticsQuery(
            metric="delay_rate", dimension="carrier", sort="desc"
        )
    )
    values = [row["value"] for row in result.chart.rows]
    assert values == sorted(values, reverse=True)
    assert "leading carrier" in result.answer.lower()


def test_forecast_overall_and_category():
    overall = run_forecast(ForecastQuery(scope="overall", horizon=4))
    category = run_forecast(
        ForecastQuery(scope="category", category="PAPER", horizon=2)
    )
    assert len(overall.table["rows"]) == 4
    assert len(category.table["rows"]) == 2
    assert all(row["forecast"] >= 0 for row in overall.table["rows"])
    assert overall.meta["inventory_recommendation"] >= overall.table["rows"][0]["forecast"]


def test_unknown_forecast_category():
    with pytest.raises(ValueError, match="Unknown category"):
        run_forecast(
            ForecastQuery(scope="category", category="NOT_REAL", horizon=2)
        )


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


def test_dashboard_payload_endpoint():
    response = client.post("/api/dashboard", json={"metric": "order_count"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["order_count"] == 400
    assert set(payload["charts"]) == {"volume", "status", "carriers"}
