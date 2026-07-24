import { Braces, Info } from "lucide-react";
import type { ChartSpec } from "../lib/types";
import { Badge } from "./ui";

export function ChartExplainability({ spec }: { spec: ChartSpec }) {
  if (!spec.query_plan || !spec.explainability) return null;
  const explanation = spec.explainability;
  return (
    <details className="group mt-2 rounded-xl border border-white/7 bg-black/10">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs font-medium text-[#91a39d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]">
        <Info size={13} /> How this chart was calculated
      </summary>
      <div className="grid gap-3 border-t border-white/7 p-3 text-xs text-[#93a49e]">
        <p>{explanation.metric_definition}</p>
        <div className="flex flex-wrap gap-2">
          <Badge>{explanation.metric.replaceAll("_", " ")}</Badge>
          {explanation.dimensions.map((dimension) => <Badge key={dimension}>{dimension}</Badge>)}
        </div>
        <details>
          <summary className="flex cursor-pointer items-center gap-2 text-[#aebdb8]">
            <Braces size={13} /> Query plan
          </summary>
          <pre className="mt-2 overflow-auto rounded-lg bg-black/20 p-3 text-[11px]">
            {JSON.stringify(spec.query_plan, null, 2)}
          </pre>
        </details>
        {explanation.warnings.map((warning) => (
          <p key={warning} className="text-[#dfb677]">Note: {warning}</p>
        ))}
      </div>
    </details>
  );
}
