import { describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("API client", () => {
  it("maps dashboard filters into a validated request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ kpis: {}, charts: {}, table: {}, data_anchor: "2025-12-30" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await api.dashboard({
      start_date: "2025-01-01",
      end_date: "2025-12-30",
      carriers: ["DHL"],
      regions: [],
      warehouses: [],
      categories: [],
      statuses: [],
    });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body)).filters.carriers).toEqual(["DHL"]);
    fetchMock.mockRestore();
  });

  it("maps SKU forecasts without sending a category", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ kind: "result" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await api.forecast("sku", "PAPER-0197", 2);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      scope: "sku",
      category: null,
      sku: "PAPER-0197",
      horizon: 2,
    });
    fetchMock.mockRestore();
  });

  it("surfaces FastAPI validation details as readable errors", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ msg: "Invalid SKU" }] }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(api.forecast("sku", "UNKNOWN", 2)).rejects.toThrow("Invalid SKU");
    fetchMock.mockRestore();
  });
});
