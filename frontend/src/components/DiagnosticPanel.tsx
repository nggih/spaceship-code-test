import { useState } from "react";
import { SearchCheck } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResult, Filters } from "../lib/types";
import { Button, Card, Skeleton } from "./ui";
import { ResultPanel } from "./ResultPanel";

export function DiagnosticPanel({ filters }: { filters: Filters }) {
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      setResult(await api.diagnostics(filters));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Diagnostic analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-white/8 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[#f4a261]">
            <SearchCheck size={17} />
            <span className="text-xs font-semibold uppercase tracking-[.18em]">Delay diagnostics</span>
          </div>
          <h2 className="text-xl font-semibold">Find where delays concentrate</h2>
          <p className="mt-2 text-sm text-[#82938e]">
            Compares carrier, region, warehouse, category, and promotion segments under the active filters.
          </p>
        </div>
        <Button onClick={run} disabled={loading}>
          {loading ? "Analyzing…" : "Analyze delay drivers"}
        </Button>
      </div>
      {(loading || error || result) && (
        <div className="p-5 sm:p-6">
          {error && <p role="alert" className="text-sm text-[#f5b1b4]">{error}</p>}
          {loading && <div className="grid gap-3"><Skeleton className="h-20" /><Skeleton className="h-72" /></div>}
          {result && !loading && <ResultPanel result={result} />}
        </div>
      )}
    </Card>
  );
}
