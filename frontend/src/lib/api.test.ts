import { beforeEach, describe, expect, it, vi } from "vitest";
import { aiSession, api } from "./api";

describe("API client", () => {
  beforeEach(() => {
    aiSession.clear();
    vi.restoreAllMocks();
  });

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

  it("sends bounded chat history and rotates the AI session header", async () => {
    aiSession.set("existing-session");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          kind: "clarification",
          message: "Which region?",
          suggestions: [],
          query_plan: { intent: "clarification" },
          meta: {},
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "X-AI-Session": "rotated-session",
          },
        },
      ),
    );
    await api.ask("Now compare that by region", undefined, [
      { role: "user", content: "Which carrier has the highest delay rate?" },
      { role: "assistant", content: "GLS had the highest delay rate." },
    ]);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-AI-Session"]).toBe(
      "existing-session",
    );
    expect(JSON.parse(String(init.body))).toMatchObject({
      question: "Now compare that by region",
      history: [
        { role: "user", content: "Which carrier has the highest delay rate?" },
        { role: "assistant", content: "GLS had the highest delay rate." },
      ],
    });
    expect(JSON.parse(String(init.body))).not.toHaveProperty("turnstile_token");
    expect(aiSession.get()).toBe("rotated-session");
  });
});
