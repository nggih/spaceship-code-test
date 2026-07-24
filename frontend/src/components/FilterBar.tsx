import { RotateCcw } from "lucide-react";
import type { Filters, Metadata } from "../lib/types";
import { Button } from "./ui";

type Props = {
  metadata: Metadata;
  filters: Filters;
  onChange: (filters: Filters) => void;
  onReset: () => void;
};

export function FilterBar({ metadata, filters, onChange, onReset }: Props) {
  const select = (
    label: string,
    key: "carriers" | "regions" | "warehouses" | "categories" | "statuses",
  ) => (
    <label className="grid gap-1.5 text-xs font-medium text-[#82938e]">
      {label}
      <select
        className="min-w-32 rounded-xl border border-white/10 bg-[#101e1b] px-3 py-2.5 text-sm text-[#e8f0ed] outline-none focus:border-[#b9f55b]/60"
        value={filters[key][0] || ""}
        onChange={(event) =>
          onChange({ ...filters, [key]: event.target.value ? [event.target.value] : [] })
        }
      >
        <option value="">All</option>
        {metadata.filters[key].map((value) => (
          <option key={value}>{value}</option>
        ))}
      </select>
    </label>
  );
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1.5 text-xs font-medium text-[#82938e]">
        From
        <input
          type="date"
          min={metadata.date_range.min}
          max={metadata.date_range.max}
          value={filters.start_date}
          onChange={(event) => onChange({ ...filters, start_date: event.target.value })}
          className="rounded-xl border border-white/10 bg-[#101e1b] px-3 py-2 text-sm text-[#e8f0ed] outline-none focus:border-[#b9f55b]/60"
        />
      </label>
      <label className="grid gap-1.5 text-xs font-medium text-[#82938e]">
        To
        <input
          type="date"
          min={metadata.date_range.min}
          max={metadata.date_range.max}
          value={filters.end_date}
          onChange={(event) => onChange({ ...filters, end_date: event.target.value })}
          className="rounded-xl border border-white/10 bg-[#101e1b] px-3 py-2 text-sm text-[#e8f0ed] outline-none focus:border-[#b9f55b]/60"
        />
      </label>
      {select("Carrier", "carriers")}
      {select("Region", "regions")}
      {select("Warehouse", "warehouses")}
      {select("Category", "categories")}
      {select("Status", "statuses")}
      <Button variant="ghost" onClick={onReset} aria-label="Reset all filters">
        <RotateCcw size={15} /> Reset
      </Button>
    </div>
  );
}

