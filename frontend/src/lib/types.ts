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
};

export type AnalyticsResult = {
  answer: string;
  query_plan: Record<string, unknown>;
  chart: ChartSpec;
  table: { columns: string[]; rows: Record<string, unknown>[] };
  explainability: {
    filters: Record<string, unknown>;
    metric: string;
    metric_definition: string;
    dimensions: string[];
    data_anchor: string;
    warnings: string[];
  };
  meta: Record<string, unknown>;
};

export type Metadata = {
  row_count: number;
  date_range: { min: string; max: string };
  filters: {
    carriers: string[];
    regions: string[];
    warehouses: string[];
    categories: string[];
    statuses: string[];
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

