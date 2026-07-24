import type { AnalyticsResult, DashboardData, Filters, Metadata } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
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
  forecast: (scope: "overall" | "category", category: string | null, horizon: number) =>
    request<AnalyticsResult>("/api/forecast", {
      method: "POST",
      body: JSON.stringify({ scope, category, horizon }),
    }),
  ask: (question: string, turnstileToken?: string) =>
    request<AnalyticsResult>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, turnstile_token: turnstileToken }),
    }),
};

