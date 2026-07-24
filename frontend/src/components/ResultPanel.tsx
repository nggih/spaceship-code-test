import { Braces, Database, Info } from "lucide-react";
import type { AnalyticsResult } from "../lib/types";
import { LazyChart } from "./LazyChart";
import { Badge, Card } from "./ui";

export function ResultPanel({ result }: { result: AnalyticsResult }) {
  const columns = result.table.columns || Object.keys(result.table.rows[0] || {});
  return (
    <div className="grid gap-4">
      <div className="rounded-xl border border-[#b9f55b]/15 bg-[#b9f55b]/5 p-4 text-sm leading-6 text-[#e5f0ec]">
        {result.answer}
      </div>
      {result.chart.rows.length > 0 && <LazyChart spec={result.chart} height={280} />}
      <details className="group rounded-xl border border-white/8 bg-black/10">
        <summary className="flex cursor-pointer list-none items-center gap-2 p-3 text-sm font-semibold text-[#c7d3cf]">
          <Braces size={15} /> Structured interpretation
        </summary>
        <pre className="overflow-auto border-t border-white/8 p-4 text-xs text-[#9fb1ab]">
          {JSON.stringify(result.query_plan, null, 2)}
        </pre>
      </details>
      <div className="flex flex-wrap gap-2">
        <Badge>{result.explainability.metric.replaceAll("_", " ")}</Badge>
        {result.explainability.dimensions.map((dimension) => (
          <Badge key={dimension}>{dimension}</Badge>
        ))}
        {Object.entries(result.explainability.filters).map(([key, value]) => (
          <Badge key={key}>{key}: {String(value)}</Badge>
        ))}
      </div>
      <p className="flex items-start gap-2 text-xs leading-5 text-[#93a49e]">
        <Info size={14} className="mt-0.5 shrink-0" />
        {result.explainability.metric_definition}
      </p>
      <p className="text-xs text-[#93a49e]">
        Dataset date anchor: {result.explainability.data_anchor}
        {result.meta.model ? ` · Routed AI model: ${String(result.meta.model)}` : ""}
        {typeof result.meta.cache_hit === "boolean" ? ` · Cache: ${result.meta.cache_hit ? "hit" : "miss"}` : ""}
      </p>
      {result.table.rows.length > 0 && (
        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-white/8 px-4 py-3 text-sm font-semibold">
            <Database size={15} /> Underlying result
          </div>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-[#101e1b] text-[#93a49e]">
                <tr>{columns.map((column) => <th key={column} className="px-4 py-3 font-medium">{column}</th>)}</tr>
              </thead>
              <tbody>
                {result.table.rows.map((row, index) => (
                  <tr key={index} className="border-t border-white/5 text-[#c6d2ce]">
                    {columns.map((column) => <td key={column} className="px-4 py-3">{String(row[column] ?? "—")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {result.explainability.warnings.map((warning) => (
        <p key={warning} className="text-xs leading-5 text-[#dfb677]">Note: {warning}</p>
      ))}
    </div>
  );
}
