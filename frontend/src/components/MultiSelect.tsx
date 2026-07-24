import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

type Props = {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
};

export function MultiSelect({ label, options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const handlePointer = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const handleKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKeyboard);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKeyboard);
    };
  }, [open]);

  const toggle = (value: string) =>
    onChange(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value],
    );

  const summary =
    selected.length === 0
      ? "All"
      : selected.length === 1
        ? selected[0]
        : `${selected.length} selected`;

  return (
    <div ref={root} className="relative grid gap-1.5">
      <span className="text-xs font-medium text-[#9db0aa]">{label}</span>
      <div className="relative flex min-w-36">
        <button
          type="button"
          aria-label={`${label} filter, ${summary}`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((value) => !value)}
          className="flex w-full items-center justify-between gap-2 rounded-xl border border-white/10 bg-[#101e1b] px-3 py-2.5 text-sm text-[#e8f0ed] outline-none transition focus-visible:border-[#b9f55b]/60 focus-visible:ring-2 focus-visible:ring-[#b9f55b]/30 aria-expanded:border-[#b9f55b]/60"
        >
          <span className={selected.length ? "text-[#e8f0ed]" : "text-[#8a9b95]"}>{summary}</span>
          <ChevronDown size={15} className="text-[#9db0aa]" />
        </button>
        {selected.length > 0 && (
          <button
            type="button"
            aria-label={`Clear ${label}`}
            onClick={() => onChange([])}
            className="absolute right-7 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded text-[#9db0aa] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
          >
            <X size={13} />
          </button>
        )}
      </div>
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          aria-multiselectable="true"
          className="absolute top-full z-20 mt-1.5 max-h-60 w-full min-w-44 overflow-auto rounded-xl border border-white/12 bg-[#0d1917] p-1 shadow-[0_24px_70px_rgba(0,0,0,.5)]"
        >
          {options.map((value) => {
            const active = selected.includes(value);
            return (
              <li key={value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => toggle(value)}
                  className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-[#cdd9d4] hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                >
                  <span>{value}</span>
                  <span
                    className={`grid h-4 w-4 place-items-center rounded border ${
                      active ? "border-[#b9f55b] bg-[#b9f55b] text-[#07110f]" : "border-white/20"
                    }`}
                  >
                    {active && <Check size={12} strokeWidth={3} />}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
