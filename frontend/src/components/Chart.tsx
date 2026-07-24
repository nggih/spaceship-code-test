import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import type { ChartSpec } from "../lib/types";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  SVGRenderer,
]);

const colors = ["#b9f55b", "#49dcb1", "#f4a261", "#df6f74", "#78a7ff"];

export function Chart({ spec, height = 300 }: { spec: ChartSpec; height?: number }) {
  const labels = spec.rows.map((row) => String(row[spec.x_key] ?? ""));
  const base: EChartsOption = {
    color: colors,
    animationDuration: 500,
    grid: { left: 48, right: 20, top: 36, bottom: 48 },
    tooltip: { trigger: spec.type === "pie" ? "item" : "axis" },
    textStyle: { color: "#aabbb6", fontFamily: "Inter, ui-sans-serif" },
  };
  let option: EChartsOption;

  if (spec.type === "pie") {
    option = {
      ...base,
      legend: { bottom: 0, textStyle: { color: "#aabbb6" } },
      series: [
        {
          type: "pie",
          radius: ["48%", "72%"],
          center: ["50%", "43%"],
          label: { color: "#dce8e4" },
          data: spec.rows.map((row) => ({
            name: String(row[spec.x_key]),
            value: Number(row[spec.y_keys[0]] ?? 0),
          })),
        },
      ],
    };
  } else {
    const horizontal = spec.type === "horizontal_bar";
    const categoryAxis = {
      type: "category" as const,
      data: labels,
      axisLabel: { color: "#80928d", hideOverlap: true },
      axisLine: { lineStyle: { color: "#273733" } },
    };
    const valueAxis = {
      type: "value" as const,
      axisLabel: { color: "#80928d" },
      splitLine: { lineStyle: { color: "#192824" } },
    };
    option = {
      ...base,
      legend:
        spec.y_keys.length > 1
          ? { top: 0, textStyle: { color: "#aabbb6" } }
          : undefined,
      xAxis: horizontal ? valueAxis : categoryAxis,
      yAxis: horizontal ? categoryAxis : valueAxis,
      series: spec.y_keys.map((key, index) => ({
        name: key.replaceAll("_", " "),
        type: spec.type === "line" ? "line" : "bar",
        smooth: spec.type === "line",
        showSymbol: false,
        connectNulls: false,
        areaStyle:
          spec.type === "line" && index === 0 ? { opacity: 0.08 } : undefined,
        lineStyle: index === 1 ? { type: "dashed", width: 3 } : { width: 3 },
        itemStyle: { borderRadius: horizontal ? [0, 5, 5, 0] : [5, 5, 0, 0] },
        data: spec.rows.map((row) => {
          const value = row[key];
          return value === null ? null : Number(value);
        }),
      })),
    };
  }
  return (
    <ReactEChartsCore
      echarts={echarts}
      option={option}
      style={{ height }}
      opts={{ renderer: "svg" }}
      notMerge
      aria-label={spec.title}
    />
  );
}
