import { useEffect, useRef, useState } from "react";
import { ArrowUp, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResult } from "../lib/types";
import { Button, Card, Skeleton } from "./ui";
import { ResultPanel } from "./ResultPanel";

declare global {
  interface Window {
    turnstile?: {
      render: (element: HTMLElement, options: Record<string, unknown>) => string;
      reset: (id: string) => void;
    };
  }
}

const examples = [
  "Show delayed orders by week for the last 3 months",
  "Which carrier has the highest delay rate?",
  "How many orders were delivered late last month?",
];

export function AIPanel() {
  const [question, setQuestion] = useState(examples[0]);
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string>();
  const widget = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | undefined>(undefined);
  const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;

  useEffect(() => {
    if (!siteKey || !widget.current) return;
    const timer = window.setInterval(() => {
      if (window.turnstile && widget.current && !widgetId.current) {
        widgetId.current = window.turnstile.render(widget.current, {
          sitekey: siteKey,
          size: "flexible",
          callback: (value: string) => setToken(value),
          "expired-callback": () => setToken(undefined),
        });
        window.clearInterval(timer);
      }
    }, 200);
    return () => window.clearInterval(timer);
  }, [siteKey]);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      setResult(await api.ask(question.trim(), token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The query could not be completed.");
    } finally {
      setLoading(false);
      if (widgetId.current) window.turnstile?.reset(widgetId.current);
      setToken(undefined);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-white/8 p-5 sm:p-6">
        <div className="mb-2 flex items-center gap-2 text-[#d9ff9f]">
          <Sparkles size={17} />
          <span className="text-xs font-semibold uppercase tracking-[.18em]">Ask Logistics AI</span>
        </div>
        <h2 className="text-xl font-semibold tracking-tight">Question in. Computed answer out.</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#82938e]">
          AI interprets your question; validated tools calculate every result from the dataset.
        </p>
      </div>
      <div className="grid gap-5 p-5 sm:p-6">
        <div className="flex flex-wrap gap-2">
          {examples.map((example) => (
            <button
              key={example}
              onClick={() => setQuestion(example)}
              className="rounded-full border border-white/9 px-3 py-1.5 text-left text-xs text-[#9fb0ab] transition hover:border-[#b9f55b]/30 hover:text-white"
            >
              {example}
            </button>
          ))}
        </div>
        <div className="flex items-end gap-3 rounded-2xl border border-white/10 bg-[#081310] p-2 focus-within:border-[#b9f55b]/40">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (!loading && question.trim()) void submit();
              }
            }}
            rows={2}
            maxLength={500}
            aria-label="Ask a logistics analytics question"
            className="min-h-14 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-[#596964]"
            placeholder="Ask about orders, delays, carriers, regions, or demand…"
          />
          <Button
            onClick={submit}
            disabled={loading || !question.trim() || Boolean(siteKey && !token)}
            className="h-11 w-11 rounded-xl p-0"
            aria-label="Submit question"
          >
            <ArrowUp size={18} />
          </Button>
        </div>
        <div ref={widget} />
        {error && (
          <div role="alert" className="rounded-xl border border-[#df6f74]/25 bg-[#df6f74]/8 p-4 text-sm text-[#f5b1b4]">
            {error}
          </div>
        )}
        {loading && <div className="grid gap-3"><Skeleton className="h-20" /><Skeleton className="h-64" /></div>}
        {result && !loading && <ResultPanel result={result} />}
      </div>
    </Card>
  );
}
