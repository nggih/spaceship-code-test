import type { AnalyticsResult, AskResult, DashboardData, Filters, Metadata } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || "Invalid request").join("; ")
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  health: () =>
    request<{
      status: string;
      dataset_rows: number;
      data_max_date: string;
      ai_configured: boolean;
    }>("/api/health"),
  metadata: () => request<Metadata>("/api/metadata"),
  dashboard: (filters: Filters) =>
    request<DashboardData>("/api/dashboard", {
      method: "POST",
      body: JSON.stringify({ metric: "order_count", filters }),
    }),
  forecast: (
    scope: "overall" | "category" | "sku",
    selection: string | null,
    horizon: number,
  ) =>
    request<AnalyticsResult>("/api/forecast", {
      method: "POST",
      body: JSON.stringify({
        scope,
        category: scope === "category" ? selection : null,
        sku: scope === "sku" ? selection : null,
        horizon,
      }),
    }),
  diagnostics: (filters: Filters) =>
    request<AnalyticsResult>("/api/diagnostics", {
      method: "POST",
      body: JSON.stringify({ filters, minimum_sample: 5, limit: 10 }),
    }),
  ask: (question: string, turnstileToken?: string) =>
    request<AskResult>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, turnstile_token: turnstileToken }),
    }),
};
