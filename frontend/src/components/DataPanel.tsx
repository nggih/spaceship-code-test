import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button, Card, Skeleton } from "./ui";

type SourceRow = Record<string, string | number | boolean | null>;

const PAGE_SIZE = 25;

const columns = [
  { key: "client_id", label: "Client ID" },
  { key: "order_id", label: "Order ID" },
  { key: "order_date", label: "Order date" },
  { key: "delivery_date", label: "Delivery date" },
  { key: "status", label: "Status" },
  { key: "carrier", label: "Carrier" },
  { key: "origin_city", label: "Origin" },
  { key: "destination_city", label: "Destination" },
  { key: "region", label: "Region" },
  { key: "warehouse", label: "Warehouse" },
  { key: "sku", label: "SKU" },
  { key: "product_category", label: "Category" },
  { key: "quantity", label: "Quantity" },
  { key: "unit_price_usd", label: "Unit price" },
  { key: "order_value_usd", label: "Order value" },
  { key: "is_promo", label: "Promo" },
  { key: "promo_discount_pct", label: "Discount" },
] as const;

function displayValue(key: string, value: SourceRow[string]) {
  if (value === null || value === "") return "—";
  if (key === "unit_price_usd" || key === "order_value_usd") {
    return `$${Number(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  if (key === "is_promo") return value ? "Yes" : "No";
  if (key === "promo_discount_pct") return `${value}%`;
  return String(value);
}

export function DataPanel({
  rows,
  total,
  loading,
}: {
  rows: SourceRow[];
  total: number;
  loading: boolean;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const matchingRows = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    if (!term) return rows;
    return rows.filter((row) =>
      columns.some(({ key }) =>
        String(row[key] ?? "")
          .toLocaleLowerCase()
          .includes(term),
      ),
    );
  }, [rows, search]);
  const pageCount = Math.max(1, Math.ceil(matchingRows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const firstIndex = (currentPage - 1) * PAGE_SIZE;
  const visibleRows = matchingRows.slice(firstIndex, firstIndex + PAGE_SIZE);
  const firstShown = matchingRows.length ? firstIndex + 1 : 0;
  const lastShown = Math.min(firstIndex + PAGE_SIZE, matchingRows.length);

  if (loading) {
    return (
      <Card className="p-5">
        <Skeleton className="h-[520px]" />
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-white/8 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-semibold">Source records</h2>
          <p className="mt-1 text-xs text-[#93a49e]">
            {total.toLocaleString()} filtered records · read-only
          </p>
        </div>
        <label className="relative block w-full sm:max-w-sm">
          <span className="sr-only">Search source data</span>
          <Search
            aria-hidden="true"
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#71837d]"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search orders, SKUs, cities…"
            className="h-10 w-full rounded-xl border border-white/10 bg-[#07110f] pl-9 pr-3 text-sm text-white outline-none placeholder:text-[#60736d] focus:border-[#b9f55b]/50 focus:ring-2 focus:ring-[#b9f55b]/10"
          />
        </label>
      </div>

      {visibleRows.length ? (
        <div className="max-h-[580px] overflow-auto">
          <table className="w-full min-w-[1900px] text-left text-xs">
            <thead className="sticky top-0 z-10 bg-[#101e1b] text-[#93a49e] shadow-[0_1px_0_rgba(255,255,255,.08)]">
              <tr>
                {columns.map(({ key, label }) => (
                  <th key={key} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, index) => (
                <tr
                  key={String(row.order_id ?? index)}
                  className="border-t border-white/5 text-[#bdcbc6] hover:bg-white/[.025]"
                >
                  {columns.map(({ key }) => (
                    <td key={key} className="whitespace-nowrap px-4 py-3">
                      {key === "status" ? (
                        <span className="rounded-full border border-white/10 bg-white/[.03] px-2 py-1 capitalize">
                          {displayValue(key, row[key])}
                        </span>
                      ) : (
                        displayValue(key, row[key])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid min-h-64 place-items-center p-8 text-center">
          <div>
            <p className="font-medium">No matching records</p>
            <p className="mt-2 text-xs text-[#93a49e]">
              Adjust the source-data search or operational filters.
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 border-t border-white/8 p-4 text-xs text-[#93a49e] sm:flex-row sm:items-center sm:justify-between">
        <p>
          Showing {firstShown.toLocaleString()}–{lastShown.toLocaleString()} of{" "}
          {matchingRows.length.toLocaleString()} rows
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            aria-label="Previous data page"
            disabled={currentPage === 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            <ChevronLeft size={15} /> Previous
          </Button>
          <span className="min-w-20 text-center">
            Page {currentPage} of {pageCount}
          </span>
          <Button
            variant="secondary"
            aria-label="Next data page"
            disabled={currentPage === pageCount}
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
          >
            Next <ChevronRight size={15} />
          </Button>
        </div>
      </div>
    </Card>
  );
}
