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
});
