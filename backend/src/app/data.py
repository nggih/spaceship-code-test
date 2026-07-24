from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from .embedded_data import CSV_DATA

@dataclass(frozen=True, slots=True)
class Order:
    client_id: str
    order_id: str
    order_date: date
    delivery_date: date | None
    carrier: str
    origin_city: str
    destination_city: str
    status: str
    sku: str
    product_category: str
    quantity: int
    unit_price_usd: float
    order_value_usd: float
    is_promo: bool
    promo_discount_pct: int
    region: str
    warehouse: str


def _default_data_path() -> Path:
    bundled = Path(__file__).resolve().parent / "assets" / "mock_logistics_data.csv"
    if bundled.exists():
        return bundled
    return Path(__file__).resolve().parents[2] / "data" / "mock_logistics_data.csv"


@lru_cache(maxsize=1)
def load_orders(path: str | None = None) -> tuple[Order, ...]:
    data_path = Path(path or os.getenv("DATA_PATH", str(_default_data_path())))
    handle = (
        data_path.open(newline="", encoding="utf-8")
        if data_path.exists()
        else io.StringIO(CSV_DATA)
    )
    with handle:
        return tuple(
            Order(
                client_id=row["client_id"],
                order_id=row["order_id"],
                order_date=date.fromisoformat(row["order_date"]),
                delivery_date=(
                    date.fromisoformat(row["delivery_date"])
                    if row["delivery_date"]
                    else None
                ),
                carrier=row["carrier"],
                origin_city=row["origin_city"],
                destination_city=row["destination_city"],
                status=row["status"],
                sku=row["sku"],
                product_category=row["product_category"],
                quantity=int(row["quantity"]),
                unit_price_usd=float(row["unit_price_usd"]),
                order_value_usd=float(row["order_value_usd"]),
                is_promo=row["is_promo"] == "1",
                promo_discount_pct=int(row["promo_discount_pct"]),
                region=row["region"],
                warehouse=row["warehouse"],
            )
            for row in csv.DictReader(handle)
        )


ORDERS = load_orders()
DATA_MIN_DATE = min(order.order_date for order in ORDERS)
DATA_MAX_DATE = max(order.order_date for order in ORDERS)


def metadata() -> dict[str, object]:
    def values(field: str) -> list[str]:
        return sorted({str(getattr(order, field)) for order in ORDERS})

    return {
        "row_count": len(ORDERS),
        "date_range": {"min": DATA_MIN_DATE, "max": DATA_MAX_DATE},
        "filters": {
            "carriers": values("carrier"),
            "regions": values("region"),
            "warehouses": values("warehouse"),
            "categories": values("product_category"),
            "statuses": values("status"),
            "skus": values("sku"),
        },
        "metrics": [
            "order_count",
            "delivered_orders",
            "delayed_orders",
            "on_time_rate",
            "average_delivery_time",
            "demand",
            "revenue",
            "delay_rate",
        ],
        "dimensions": [
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
        ],
    }
