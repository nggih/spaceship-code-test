import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalyticsResult } from "../lib/types";
import { ResultPanel } from "./ResultPanel";

const result: AnalyticsResult = {
  kind: "result",
  answer: "Forecast demand is 90 units next month.",
  query_plan: { scope: "overall", method: "auto" },
  chart: {
    type: "table",
    title: "Forecast",
    x_key: "month",
    y_keys: ["forecast"],
    rows: [{ month: "2026-01", forecast: 90 }],
  },
  table: {
    columns: ["month", "forecast"],
    rows: [{ month: "2026-01", forecast: 90 }],
  },
  explainability: {
    filters: { scope: "overall" },
    metric: "demand",
    metric_definition: "Monthly quantity forecast.",
    dimensions: ["month"],
    data_anchor: "2025-12-30",
    warnings: [],
  },
  meta: {
    requested_method: "auto",
    inventory_recommendation: 104,
    safety_stock_percent: 15,
    supporting_orders: 400,
    candidate_scores: [
      {
        method: "moving_average_3",
        label: "3-month moving average",
        mae: 29.44,
        selected: true,
      },
      {
        method: "linear_trend",
        label: "Ordinary least-squares linear trend",
        mae: 41.44,
        selected: false,
      },
    ],
  },
};

describe("ResultPanel", () => {
  it("shows forecast model comparison and inventory evidence", () => {
    render(<ResultPanel result={result} />);

    expect(screen.getByText("Forecast model selection")).toBeInTheDocument();
    expect(screen.getByText("Auto selected")).toBeInTheDocument();
    expect(screen.getByText("3-month moving average")).toBeInTheDocument();
    expect(screen.getByText("29.44")).toBeInTheDocument();
    expect(screen.getByText(/104 units/)).toBeInTheDocument();
  });
});
