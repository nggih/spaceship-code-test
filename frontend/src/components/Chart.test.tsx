import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Chart } from "./Chart";

describe("Chart", () => {
  it("shows an accessible empty state", () => {
    render(
      <Chart
        spec={{
          type: "bar",
          title: "No results",
          x_key: "label",
          y_keys: ["value"],
          rows: [],
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("No matching data");
  });
});
