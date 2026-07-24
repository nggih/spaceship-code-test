import { lazy, Suspense } from "react";
import type { ChartSpec } from "../lib/types";
import { Skeleton } from "./ui";

const Chart = lazy(() =>
  import("./Chart").then((module) => ({ default: module.Chart })),
);

export function LazyChart({
  spec,
  height = 300,
}: {
  spec: ChartSpec;
  height?: number;
}) {
  return (
    <Suspense fallback={<Skeleton className="w-full" style={{ height }} />}>
      <Chart spec={spec} height={height} />
    </Suspense>
  );
}
