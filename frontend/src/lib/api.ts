import type {
  AnalyticsResult,
  AskResult,
  ConversationTurn,
  DashboardData,
  Filters,
  Metadata,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL || "";
const AI_SESSION_KEY = "logistics-ai-session";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const aiSession = {
  get: () => {
    try {
      return sessionStorage.getItem(AI_SESSION_KEY) || "";
    } catch {
      return "";
    }
  },
  set: (value: string) => {
    try {
      sessionStorage.setItem(AI_SESSION_KEY, value);
    } catch {
      // Session persistence is an optimization; Turnstile remains the fallback.
    }
  },
  clear: () => {
    try {
      sessionStorage.removeItem(AI_SESSION_KEY);
    } catch {
      // Ignore unavailable browser storage.
    }
  },
  has: () => Boolean(aiSession.get()),
};

async function request<T>(
  path: string,
  init?: RequestInit,
  onResponse?: (response: Response) => void,
): Promise<T> {
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
    throw new ApiError(message, response.status);
  }
  onResponse?.(response);
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
  ask: async (
    question: string,
    turnstileToken?: string,
    history: ConversationTurn[] = [],
  ) => {
    const session = aiSession.get();
    try {
      return await request<AskResult>(
        "/api/ask",
        {
          method: "POST",
          headers: session ? { "X-AI-Session": session } : undefined,
          body: JSON.stringify({
            question,
            turnstile_token: session ? undefined : turnstileToken,
            history,
          }),
        },
        (response) => {
          const issuedSession = response.headers.get("X-AI-Session");
          if (issuedSession) aiSession.set(issuedSession);
        },
      );
    } catch (error) {
      if (
        session &&
        error instanceof ApiError &&
        [400, 401, 403].includes(error.status)
      ) {
        aiSession.clear();
      }
      throw error;
    }
  },
};
