export type Filters = {
  start_date?: string;
  end_date?: string;
  carriers: string[];
  regions: string[];
  warehouses: string[];
  categories: string[];
  statuses: string[];
  skus?: string[];
};

export type ChartSpec = {
  type: "line" | "bar" | "horizontal_bar" | "pie" | "table";
  title: string;
  x_key: string;
  y_keys: string[];
  rows: Record<string, string | number | null>[];
  query_plan?: Record<string, unknown>;
  explainability?: Explainability;
};

export type Explainability = {
  filters: Record<string, unknown>;
  metric: string;
  metric_definition: string;
  dimensions: string[];
  data_anchor: string;
  warnings: string[];
};

export type AnalyticsResult = {
  kind: "result";
  answer: string;
  query_plan: Record<string, unknown>;
  chart: ChartSpec;
  table: { columns: string[]; rows: Record<string, unknown>[] };
  explainability: Explainability;
  meta: Record<string, unknown>;
};

export type ClarificationResult = {
  kind: "clarification";
  message: string;
  suggestions: string[];
  query_plan: Record<string, unknown>;
  meta: Record<string, unknown>;
};

export type AskResult = AnalyticsResult | ClarificationResult;

export type ConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  logout_url: string | null;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  result: AskResult | null;
  created_at: string;
};

export type ConversationDetail = Omit<ConversationSummary, "message_count"> & {
  messages: StoredMessage[];
};

export type ForecastMethod =
  | "auto"
  | "moving_average_3"
  | "linear_trend"
  | "exponential_smoothing"
  | "naive";

export type Metadata = {
  row_count: number;
  date_range: { min: string; max: string };
  filters: {
    carriers: string[];
    regions: string[];
    warehouses: string[];
    categories: string[];
    statuses: string[];
    skus: string[];
  };
};

export type DashboardData = {
  kpis: Record<string, number>;
  charts: {
    volume: ChartSpec;
    status: ChartSpec;
    carriers: ChartSpec;
  };
  table: {
    rows: Record<string, string | number>[];
    total: number;
  };
  data_anchor: string;
};
