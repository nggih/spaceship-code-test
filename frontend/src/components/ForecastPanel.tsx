import { useEffect, useMemo, useState } from "react";
import { TrendingUp } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResult } from "../lib/types";
import { Card, Skeleton } from "./ui";
import { ResultPanel } from "./ResultPanel";

export function ForecastPanel({ categories, skus }: { categories: string[]; skus: string[] }) {
  const [scope, setScope] = useState<"overall" | "category" | "sku">("overall");
  const [category, setCategory] = useState(categories[0] || "");
  const [sku, setSku] = useState(skus[0] || "");
  const [horizon, setHorizon] = useState(3);
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const skuSet = useMemo(() => new Set(skus), [skus]);
  const skuReady = scope !== "sku" || skuSet.has(sku);

  useEffect(() => {
    if (!skuReady) return;
    const selection = scope === "category" ? category : scope === "sku" ? sku : null;
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      api
        .forecast(scope, selection, horizon)
        .then((response) => {
          if (active) setResult(response);
        })
        .catch((caught) => {
          if (active) setError(caught instanceof Error ? caught.message : "Forecast failed.");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 300);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [scope, category, sku, horizon, skuReady]);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-white/8 p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[#49dcb1]">
            <TrendingUp size={17} />
            <span className="text-xs font-semibold uppercase tracking-[.18em]">Demand planning</span>
          </div>
          <h2 className="text-xl font-semibold">Forecast and inventory guide</h2>
          <p className="mt-2 text-sm text-[#93a49e]">
            Updates automatically as you change scope or horizon.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs text-[#9db0aa]">
            Scope
            <select className="control" value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}>
              <option value="overall">Overall</option>
              <option value="category">Category</option>
              <option value="sku">SKU</option>
            </select>
          </label>
          {scope === "category" && (
            <label className="grid gap-1 text-xs text-[#9db0aa]">
              Category
              <select className="control" value={category} onChange={(e) => setCategory(e.target.value)}>
                {categories.map((value) => <option key={value}>{value}</option>)}
              </select>
            </label>
          )}
          {scope === "sku" && (
            <label className="grid gap-1 text-xs text-[#9db0aa]">
              SKU
              <input
                className="control w-44"
                list="forecast-skus"
                value={sku}
                onChange={(event) => setSku(event.target.value.toUpperCase())}
                placeholder="e.g. PAPER-0197"
              />
              <datalist id="forecast-skus">
                {skus.map((value) => <option key={value} value={value} />)}
              </datalist>
            </label>
          )}
          <label className="grid gap-1 text-xs text-[#9db0aa]">
            Horizon
            <select className="control" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {[1, 2, 3, 4, 5, 6].map((value) => <option key={value} value={value}>{value} months</option>)}
            </select>
          </label>
        </div>
      </div>
      <div className="p-5 sm:p-6">
        {scope === "sku" && !skuReady && (
          <p className="text-sm text-[#dfb677]">Enter a known SKU (pick from the list) to forecast.</p>
        )}
        {error && <p role="alert" className="text-sm text-[#f5b1b4]">{error}</p>}
        {loading && skuReady && <div className="grid gap-3"><Skeleton className="h-20" /><Skeleton className="h-72" /></div>}
        {result && !loading && skuReady && <ResultPanel result={result} />}
      </div>
    </Card>
  );
}
