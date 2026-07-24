import { useEffect, useMemo, useState } from "react";
import { Activity, Box, CheckCircle2, Clock3, PackageCheck, TriangleAlert } from "lucide-react";
import { api } from "./lib/api";
import type { DashboardData, Filters, Metadata } from "./lib/types";
import { AIPanel } from "./components/AIPanel";
import { Chart } from "./components/Chart";
import { FilterBar } from "./components/FilterBar";
import { ForecastPanel } from "./components/ForecastPanel";
import { Badge, Card, Skeleton } from "./components/ui";

const emptyFilters: Filters = {
  start_date: "2025-01-01",
  end_date: "2025-12-30",
  carriers: [],
  regions: [],
  warehouses: [],
  categories: [],
  statuses: [],
};

const kpiConfig = [
  { key: "order_count", label: "Total orders", icon: Box, format: (v: number) => v.toLocaleString() },
  { key: "delivered_orders", label: "Delivered", icon: PackageCheck, format: (v: number) => v.toLocaleString() },
  { key: "delayed_orders", label: "Delayed", icon: TriangleAlert, format: (v: number) => v.toLocaleString() },
  { key: "on_time_rate", label: "On-time rate", icon: CheckCircle2, format: (v: number) => `${v.toFixed(1)}%` },
  { key: "average_delivery_time", label: "Avg. delivery", icon: Clock3, format: (v: number) => `${v.toFixed(1)} days` },
];

export default function App() {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [health, setHealth] = useState<{ ai_configured: boolean } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.metadata(), api.health()])
      .then(([meta, status]) => {
        setMetadata(meta);
        setHealth(status);
        setFilters((current) => ({
          ...current,
          start_date: meta.date_range.min,
          end_date: meta.date_range.max,
        }));
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load metadata."));
  }, []);

  useEffect(() => {
    if (!metadata) return;
    const timer = window.setTimeout(() => {
      setLoading(true);
      api.dashboard(filters)
        .then(setDashboard)
        .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load dashboard."))
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [filters, metadata]);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((value) => Array.isArray(value) ? value.length : Boolean(value)).length - 2,
    [filters],
  );

  return (
    <div className="min-h-screen bg-[#07110f] text-[#edf4f1]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_80%_-10%,rgba(185,245,91,.12),transparent_30%),radial-gradient(circle_at_10%_35%,rgba(73,220,177,.07),transparent_25%)]" />
      <header className="relative border-b border-white/7">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-6 px-5 py-7 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[#b9f55b] text-[#07110f] shadow-[0_0_30px_rgba(185,245,91,.18)]">
              <Activity size={22} strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight">Logistics Intelligence</p>
              <p className="text-xs text-[#71837d]">Operational analytics · 2025 dataset</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>{metadata?.row_count || "—"} source rows</Badge>
            <span className="flex items-center gap-2 text-xs text-[#82938e]">
              <span className="h-2 w-2 rounded-full bg-[#49dcb1] shadow-[0_0_10px_#49dcb1]" />
              API online
            </span>
            <span className="flex items-center gap-2 text-xs text-[#82938e]">
              <span className={`h-2 w-2 rounded-full ${health?.ai_configured ? "bg-[#b9f55b]" : "bg-[#dfb677]"}`} />
              AI {health?.ai_configured ? "ready" : "needs key"}
            </span>
          </div>
        </div>
      </header>

      <main className="relative mx-auto grid max-w-[1480px] gap-6 px-5 py-8 sm:px-8">
        <section>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[.2em] text-[#b9f55b]">Network overview</p>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-[-.035em] sm:text-4xl">
                See where orders move.<br /><span className="text-[#80928d]">Understand where they slow down.</span>
              </h1>
            </div>
            {metadata && (
              <FilterBar
                metadata={metadata}
                filters={filters}
                onChange={setFilters}
                onReset={() => setFilters({ ...emptyFilters, start_date: metadata.date_range.min, end_date: metadata.date_range.max })}
              />
            )}
          </div>
          {activeFilterCount > 0 && <p className="mt-3 text-xs text-[#82938e]">{activeFilterCount} operational filters active</p>}
        </section>

        {error && <div role="alert" className="rounded-xl border border-[#df6f74]/25 bg-[#df6f74]/8 p-4 text-sm text-[#f5b1b4]">{error}</div>}

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {kpiConfig.map(({ key, label, icon: Icon, format }) => (
            <Card key={key} className="min-h-32 p-4 sm:p-5">
              {loading || !dashboard ? <Skeleton className="h-20" /> : (
                <>
                  <div className="flex items-center justify-between text-[#82938e]">
                    <span className="text-xs font-medium">{label}</span><Icon size={16} />
                  </div>
                  <p className="mt-5 text-2xl font-semibold tracking-tight sm:text-3xl">{format(dashboard.kpis[key])}</p>
                  <p className="mt-1 text-[11px] text-[#596964]">filtered dataset</p>
                </>
              )}
            </Card>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.45fr_.75fr]">
          <Card className="p-5">
            <div className="mb-3"><h2 className="font-semibold">Order volume</h2><p className="text-xs text-[#71837d]">Distinct orders by month</p></div>
            {loading || !dashboard ? <Skeleton className="h-[300px]" /> : <Chart spec={dashboard.charts.volume} />}
          </Card>
          <Card className="p-5">
            <div className="mb-3"><h2 className="font-semibold">Delivery status</h2><p className="text-xs text-[#71837d]">Operational outcome mix</p></div>
            {loading || !dashboard ? <Skeleton className="h-[300px]" /> : <Chart spec={dashboard.charts.status} />}
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-[.9fr_1.1fr]">
          <Card className="p-5">
            <div className="mb-3"><h2 className="font-semibold">Carrier delay rate</h2><p className="text-xs text-[#71837d]">Delayed ÷ completed orders</p></div>
            {loading || !dashboard ? <Skeleton className="h-[320px]" /> : <Chart spec={dashboard.charts.carriers} height={320} />}
          </Card>
          <Card className="overflow-hidden">
            <div className="border-b border-white/8 p-5">
              <h2 className="font-semibold">Underlying orders</h2>
              <p className="text-xs text-[#71837d]">First 100 of {dashboard?.table.total || 0} matching records</p>
            </div>
            <div className="max-h-[350px] overflow-auto">
              <table className="w-full min-w-[700px] text-left text-xs">
                <thead className="sticky top-0 bg-[#101e1b] text-[#71837d]">
                  <tr>{["order_id", "order_date", "carrier", "destination", "status", "category", "quantity", "value"].map((key) => <th key={key} className="px-4 py-3 font-medium">{key.replaceAll("_", " ")}</th>)}</tr>
                </thead>
                <tbody>
                  {dashboard?.table.rows.map((row) => (
                    <tr key={row.order_id} className="border-t border-white/5 text-[#bdcbc6] hover:bg-white/[.02]">
                      {["order_id", "order_date", "carrier", "destination", "status", "category", "quantity", "value"].map((key) => <td key={key} className="whitespace-nowrap px-4 py-3">{String(row[key])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>

        <AIPanel />
        {metadata && <ForecastPanel categories={metadata.filters.categories} />}
      </main>
      <footer className="relative mx-auto max-w-[1480px] px-5 py-10 text-xs text-[#596964] sm:px-8">
        Read-only analytics · Relative dates anchor to 30 Dec 2025 · AI interprets, tools compute
      </footer>
    </div>
  );
}

