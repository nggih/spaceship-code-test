import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResult } from "../lib/types";
import { Button, Card, Skeleton } from "./ui";
import { ResultPanel } from "./ResultPanel";

export function ForecastPanel({ categories }: { categories: string[] }) {
  const [scope, setScope] = useState<"overall" | "category">("overall");
  const [category, setCategory] = useState(categories[0] || "");
  const [horizon, setHorizon] = useState(3);
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setResult(await api.forecast(scope, scope === "category" ? category : null, horizon));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Forecast failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-white/8 p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[#49dcb1]">
            <TrendingUp size={17} />
            <span className="text-xs font-semibold uppercase tracking-[.18em]">Demand planning</span>
          </div>
          <h2 className="text-xl font-semibold">Forecast and inventory guide</h2>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs text-[#82938e]">
            Scope
            <select className="control" value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}>
              <option value="overall">Overall</option>
              <option value="category">Category</option>
            </select>
          </label>
          {scope === "category" && (
            <label className="grid gap-1 text-xs text-[#82938e]">
              Category
              <select className="control" value={category} onChange={(e) => setCategory(e.target.value)}>
                {categories.map((value) => <option key={value}>{value}</option>)}
              </select>
            </label>
          )}
          <label className="grid gap-1 text-xs text-[#82938e]">
            Horizon
            <select className="control" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {[1, 2, 3, 4, 5, 6].map((value) => <option key={value} value={value}>{value} months</option>)}
            </select>
          </label>
          <Button onClick={load} disabled={loading}>Run forecast</Button>
        </div>
      </div>
      <div className="p-5 sm:p-6">
        {error && <p role="alert" className="text-sm text-[#f5b1b4]">{error}</p>}
        {loading && <div className="grid gap-3"><Skeleton className="h-20" /><Skeleton className="h-72" /></div>}
        {result && !loading && <ResultPanel result={result} />}
      </div>
    </Card>
  );
}

