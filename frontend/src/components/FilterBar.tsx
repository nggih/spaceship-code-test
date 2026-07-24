import { RotateCcw } from "lucide-react";
import type { Filters, Metadata } from "../lib/types";
import { Button } from "./ui";
import { MultiSelect } from "./MultiSelect";

type Props = {
  metadata: Metadata;
  filters: Filters;
  onChange: (filters: Filters) => void;
  onReset: () => void;
};

type MultiKey = "carriers" | "regions" | "warehouses" | "categories" | "statuses";

const MULTI_FILTERS: { label: string; key: MultiKey }[] = [
  { label: "Carrier", key: "carriers" },
  { label: "Region", key: "regions" },
  { label: "Warehouse", key: "warehouses" },
  { label: "Category", key: "categories" },
  { label: "Status", key: "statuses" },
];

export function FilterBar({ metadata, filters, onChange, onReset }: Props) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1.5 text-xs font-medium text-[#9db0aa]">
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
      <label className="grid gap-1.5 text-xs font-medium text-[#9db0aa]">
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
      {MULTI_FILTERS.map(({ label, key }) => (
        <MultiSelect
          key={key}
          label={label}
          options={metadata.filters[key]}
          selected={filters[key]}
          onChange={(next) => onChange({ ...filters, [key]: next })}
        />
      ))}
      <Button variant="ghost" onClick={onReset} aria-label="Reset all filters">
        <RotateCcw size={15} /> Reset
      </Button>
    </div>
  );
}
