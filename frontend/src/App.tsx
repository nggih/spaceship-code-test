import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Box,
  CheckCircle2,
  Clock3,
  Database,
  LayoutDashboard,
  LogOut,
  PackageCheck,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  UserRound,
} from "lucide-react";
import { ApiError, api } from "./lib/api";
import type { AuthUser, DashboardData, Filters, Metadata } from "./lib/types";
import { AIPanel } from "./components/AIPanel";
import { ChartExplainability } from "./components/ChartExplainability";
import { DataPanel } from "./components/DataPanel";
import { DiagnosticPanel } from "./components/DiagnosticPanel";
import { FilterBar } from "./components/FilterBar";
import { ForecastPanel } from "./components/ForecastPanel";
import { LazyChart } from "./components/LazyChart";
import { LoginScreen } from "./components/LoginScreen";
import { Badge, Button, Card, Skeleton } from "./components/ui";

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

type Tab = "dashboard" | "data" | "ask" | "forecast";

const tabs: { id: Tab; label: string; icon: typeof Box }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "data", label: "Data", icon: Database },
  { id: "ask", label: "Ask AI", icon: Sparkles },
  { id: "forecast", label: "Forecast", icon: TrendingUp },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [health, setHealth] = useState<{ ai_configured: boolean } | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api.me()
      .then((identity) => setUser(identity))
      .catch((caught) => {
        if (!(caught instanceof ApiError && caught.status === 401)) {
          setAuthError(
            caught instanceof Error ? caught.message : "Unable to check authentication.",
          );
        }
      })
      .finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    const unauthorized = () => {
      setUser(null);
      setMetadata(null);
      setDashboard(null);
      setAuthError("Your session expired. Please sign in again.");
    };
    window.addEventListener("logistics:unauthorized", unauthorized);
    return () => window.removeEventListener("logistics:unauthorized", unauthorized);
  }, []);

  useEffect(() => {
    if (!user) return;
    setError("");
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
  }, [reloadKey, user]);

  useEffect(() => {
    if (!metadata) return;
    const timer = window.setTimeout(() => {
      setLoading(true);
      api.dashboard(filters)
        .then((data) => {
          setDashboard(data);
          setError("");
        })
        .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load dashboard."))
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [filters, metadata]);

  const activeFilterCount = useMemo(() => {
    const arrays: (keyof Filters)[] = ["carriers", "regions", "warehouses", "categories", "statuses"];
    let count = arrays.filter((key) => (filters[key] as string[]).length > 0).length;
    if (metadata && (filters.start_date !== metadata.date_range.min || filters.end_date !== metadata.date_range.max)) {
      count += 1;
    }
    return count;
  }, [filters, metadata]);

  async function signOut() {
    if (user?.logout_url) {
      window.location.assign(user.logout_url);
      return;
    }
    try {
      await api.logout();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign out.");
      return;
    }
    setUser(null);
    setMetadata(null);
    setDashboard(null);
    setTab("dashboard");
  }

  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#07110f] text-[#93a49e]">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#b9f55b]" />
          Checking secure session…
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        initialError={authError}
        onAuthenticated={(identity) => {
          setAuthError("");
          setUser(identity);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#07110f] text-[#edf4f1]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_80%_-10%,rgba(185,245,91,.12),transparent_30%),radial-gradient(circle_at_10%_35%,rgba(73,220,177,.07),transparent_25%)]" />
      <header className="relative border-b border-white/7">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-6 px-5 py-6 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[#b9f55b] text-[#07110f] shadow-[0_0_30px_rgba(185,245,91,.18)]">
              <Activity size={22} strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight">Logistics Intelligence</p>
              <p className="text-xs text-[#8ba39c]">Operational analytics · 2025 dataset</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>{metadata?.row_count || "—"} source rows</Badge>
            <span className="flex items-center gap-2 text-xs text-[#9db0aa]">
              <span className="h-2 w-2 rounded-full bg-[#49dcb1] shadow-[0_0_10px_#49dcb1]" />
              API online
            </span>
            <span className="flex items-center gap-2 text-xs text-[#9db0aa]">
              <span className={`h-2 w-2 rounded-full ${health?.ai_configured ? "bg-[#b9f55b]" : "bg-[#dfb677]"}`} />
              AI {health?.ai_configured ? "ready" : "needs key"}
            </span>
            {user && (
              <span className="flex items-center gap-2 rounded-full border border-white/8 px-3 py-1.5 text-xs text-[#b9c7c2]">
                <UserRound size={13} />
                <span className="max-w-48 truncate">{user.email}</span>
              </span>
            )}
            {user && (
              <button
                type="button"
                onClick={() => void signOut()}
                className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-[#93a49e] hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
              >
                <LogOut size={13} /> Sign out
              </button>
            )}
          </div>
        </div>
        <nav
          role="tablist"
          aria-label="Sections"
          className="mx-auto grid max-w-[1480px] grid-cols-4 gap-1 px-5 sm:flex sm:px-8"
        >
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`flex min-w-0 items-center justify-center gap-1 border-b-2 px-1 py-3 text-xs font-medium transition sm:gap-2 sm:px-3 sm:text-sm ${
                tab === id
                  ? "border-[#b9f55b] text-white"
                  : "border-transparent text-[#93a49e] hover:text-white"
              }`}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>
      </header>

      <main className="relative mx-auto grid max-w-[1480px] gap-6 px-5 py-8 sm:px-8">
        {error && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#df6f74]/25 bg-[#df6f74]/8 p-4 text-sm text-[#f5b1b4]">
            <span>{error}</span>
            <Button variant="secondary" onClick={() => { setError(""); setReloadKey((value) => value + 1); }}>
              Retry
            </Button>
          </div>
        )}

        {tab === "dashboard" && (
          <>
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[.2em] text-[#b9f55b]">Network overview</p>
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <h1 className="max-w-3xl text-3xl font-semibold tracking-[-.035em] sm:text-4xl">
                    See where orders move.<br /><span className="text-[#8ba39c]">Understand where they slow down.</span>
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
              {activeFilterCount > 0 && <p className="mt-3 text-xs text-[#93a49e]">{activeFilterCount} operational filters active</p>}
            </section>

            <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              {kpiConfig.map(({ key, label, icon: Icon, format }) => (
                <Card key={key} data-testid={`kpi-${key}`} className="min-h-32 p-4 sm:p-5">
                  {loading || !dashboard ? <Skeleton className="h-20" /> : (
                    <>
                      <div className="flex items-center justify-between text-[#93a49e]">
                        <span className="text-xs font-medium">{label}</span><Icon size={16} />
                      </div>
                      <p className="mt-5 text-2xl font-semibold tracking-tight sm:text-3xl">{format(dashboard.kpis[key])}</p>
                      <p className="mt-1 text-[11px] text-[#7c8d88]">filtered dataset</p>
                    </>
                  )}
                </Card>
              ))}
            </section>

            <section className="grid gap-4 lg:grid-cols-[1.45fr_.75fr]">
              <Card className="p-5">
                <div className="mb-3"><h2 className="font-semibold">Order volume</h2><p className="text-xs text-[#93a49e]">Distinct orders by month</p></div>
                {loading || !dashboard ? <Skeleton className="h-[300px]" /> : (
                  <>
                    <LazyChart spec={dashboard.charts.volume} />
                    <ChartExplainability spec={dashboard.charts.volume} />
                  </>
                )}
              </Card>
              <Card className="p-5">
                <div className="mb-3"><h2 className="font-semibold">Delivery status</h2><p className="text-xs text-[#93a49e]">Operational outcome mix</p></div>
                {loading || !dashboard ? <Skeleton className="h-[300px]" /> : (
                  <>
                    <LazyChart spec={dashboard.charts.status} />
                    <ChartExplainability spec={dashboard.charts.status} />
                  </>
                )}
              </Card>
            </section>

            <section>
              <Card className="p-5">
                <div className="mb-3"><h2 className="font-semibold">Carrier delay rate</h2><p className="text-xs text-[#93a49e]">Delayed ÷ completed orders</p></div>
                {loading || !dashboard ? <Skeleton className="h-[320px]" /> : (
                  <>
                    <LazyChart spec={dashboard.charts.carriers} height={320} />
                    <ChartExplainability spec={dashboard.charts.carriers} />
                  </>
                )}
              </Card>
            </section>

            <DiagnosticPanel filters={filters} />
          </>
        )}

        {tab === "data" && metadata && (
          <section className="grid gap-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-[.2em] text-[#49dcb1]">
                  Source data
                </p>
                <h1 className="max-w-3xl text-3xl font-semibold tracking-[-.035em] sm:text-4xl">
                  Inspect the source dataset.
                  <br />
                  <span className="text-[#8ba39c]">
                    Verify every record behind the analysis.
                  </span>
                </h1>
              </div>
              <FilterBar
                metadata={metadata}
                filters={filters}
                onChange={setFilters}
                onReset={() =>
                  setFilters({
                    ...emptyFilters,
                    start_date: metadata.date_range.min,
                    end_date: metadata.date_range.max,
                  })
                }
              />
            </div>
            {activeFilterCount > 0 && (
              <p className="text-xs text-[#93a49e]">
                {activeFilterCount} operational filters active
              </p>
            )}
            <DataPanel
              rows={dashboard?.table.rows ?? []}
              total={dashboard?.table.total ?? 0}
              loading={loading || !dashboard}
            />
          </section>
        )}

        {tab === "ask" && (
          <section className="grid gap-4">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[.2em] text-[#b9f55b]">Natural-language analysis</p>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-[-.035em] sm:text-4xl">
                Ask a question.<br /><span className="text-[#8ba39c]">Get a computed, explained answer.</span>
              </h1>
            </div>
            <AIPanel />
          </section>
        )}

        {tab === "forecast" && metadata && (
          <section className="grid gap-4">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[.2em] text-[#49dcb1]">Predictive planning</p>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-[-.035em] sm:text-4xl">
                Project demand.<br /><span className="text-[#8ba39c]">Plan inventory with a transparent method.</span>
              </h1>
            </div>
            <ForecastPanel
              categories={metadata.filters.categories}
              skus={metadata.filters.skus}
            />
          </section>
        )}
      </main>
      <footer className="relative mx-auto max-w-[1480px] px-5 py-10 text-xs text-[#7c8d88] sm:px-8">
        Read-only analytics · Relative dates anchor to 30 Dec 2025 · AI interprets, tools compute
      </footer>
    </div>
  );
}
