import { useEffect, useRef, useState } from "react";
import { ArrowUp, Clock3, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import type { AskResult } from "../lib/types";
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
  "Why are deliveries delayed?",
];
const HISTORY_KEY = "logistics-ai-query-history";

export function AIPanel() {
  const [question, setQuestion] = useState(examples[0]);
  const [result, setResult] = useState<AskResult | null>(null);
  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  });
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
    const submitted = question.trim();
    if (!submitted) return;
    setLoading(true);
    setError("");
    try {
      const response = await api.ask(submitted, token);
      setResult(response);
      setHistory((current) => {
        const next = [submitted, ...current.filter((item) => item !== submitted)].slice(0, 8);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
        return next;
      });
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
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#93a49e]">
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
        {history.length > 0 && (
          <details className="rounded-xl border border-white/7 bg-black/10">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs text-[#91a39d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]">
              <Clock3 size={13} /> Recent questions ({history.length})
            </summary>
            <div className="flex flex-wrap gap-2 border-t border-white/7 p-3">
              {history.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setQuestion(item)}
                  className="rounded-lg border border-white/8 px-3 py-2 text-left text-xs text-[#aebdb8] hover:border-[#b9f55b]/30 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                >
                  {item}
                </button>
              ))}
            </div>
          </details>
        )}
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
            className="min-h-14 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-[#7c8d88]"
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
        {result?.kind === "result" && !loading && <ResultPanel result={result} />}
        {result?.kind === "clarification" && !loading && (
          <div className="grid gap-3 rounded-xl border border-[#f4a261]/20 bg-[#f4a261]/5 p-4">
            <p className="text-sm leading-6 text-[#f3ddc7]">{result.message}</p>
            <div className="flex flex-wrap gap-2">
              {result.suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setQuestion(suggestion)}
                  className="rounded-full border border-[#f4a261]/20 px-3 py-1.5 text-left text-xs text-[#e6bd92] hover:border-[#f4a261]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
