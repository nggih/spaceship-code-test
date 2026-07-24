import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  MessageSquarePlus,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { aiSession, api } from "../lib/api";
import type { AskResult, ConversationTurn } from "../lib/types";
import { Button, Card } from "./ui";
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
const CHAT_KEY = "logistics-ai-conversation-v1";
const MAX_STORED_MESSAGES = 20;

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: AskResult;
  error?: boolean;
  retryQuestion?: string;
};

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi — I can analyze orders, delivery performance, delay patterns, and demand forecasts. Ask a question, then refine it naturally in your next message.",
};

function newId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

function isAskResult(value: unknown): value is AskResult {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { kind?: unknown };
  return candidate.kind === "result" || candidate.kind === "clarification";
}

function loadConversation(): ChatMessage[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHAT_KEY) || "[]");
    if (!Array.isArray(parsed)) return [welcomeMessage];
    const messages = parsed
      .filter(
        (message) =>
          message &&
          (message.role === "user" || message.role === "assistant") &&
          typeof message.content === "string",
      )
      .map((message) => ({
        id: typeof message.id === "string" ? message.id : newId(),
        role: message.role as "user" | "assistant",
        content: message.content as string,
        result: isAskResult(message.result) ? message.result : undefined,
        error: Boolean(message.error),
        retryQuestion:
          typeof message.retryQuestion === "string" ? message.retryQuestion : undefined,
      }))
      .slice(-MAX_STORED_MESSAGES);
    return [welcomeMessage, ...messages];
  } catch {
    return [welcomeMessage];
  }
}

function persistConversation(messages: ChatMessage[]) {
  try {
    localStorage.setItem(
      CHAT_KEY,
      JSON.stringify(messages.filter((message) => message.id !== "welcome")),
    );
  } catch {
    // Browser history is optional; the analytical result remains visible in memory.
  }
}

function appendMessages(current: ChatMessage[], ...next: ChatMessage[]) {
  const conversation = [
    ...current.filter((message) => message.id !== "welcome"),
    ...next,
  ].slice(-MAX_STORED_MESSAGES);
  return [welcomeMessage, ...conversation];
}

function conversationContext(messages: ChatMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = [];
  let pendingUser: ChatMessage | null = null;
  for (const message of messages) {
    if (message.id === "welcome" || message.error) continue;
    if (message.role === "user") {
      pendingUser = message;
      continue;
    }
    if (pendingUser) {
      turns.push(
        { role: "user", content: pendingUser.content },
        { role: "assistant", content: message.content },
      );
      pendingUser = null;
    }
  }
  return turns.slice(-8);
}

export function AIPanel() {
  const initialMessages = useRef<ChatMessage[]>(loadConversation());
  const [messages, setMessages] = useState(initialMessages.current);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string>();
  const [sessionReady, setSessionReady] = useState(() => aiSession.has());
  const widget = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | undefined>(undefined);
  const composer = useRef<HTMLTextAreaElement>(null);
  const endOfThread = useRef<HTMLDivElement>(null);
  const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;

  useEffect(() => {
    persistConversation(messages);
    endOfThread.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  useEffect(() => {
    if (sessionReady || !siteKey || !widget.current) return;
    const timer = window.setInterval(() => {
      if (window.turnstile && widget.current && !widgetId.current) {
        widgetId.current = window.turnstile.render(widget.current, {
          sitekey: siteKey,
          size: "flexible",
          callback: (value: string) => setToken(value),
          "expired-callback": () => setToken(undefined),
          "error-callback": () => setToken(undefined),
        });
        window.clearInterval(timer);
      }
    }, 200);
    return () => window.clearInterval(timer);
  }, [siteKey, sessionReady]);

  function choosePrompt(prompt: string) {
    setQuestion(prompt);
    window.setTimeout(() => composer.current?.focus(), 0);
  }

  function newConversation() {
    setMessages([welcomeMessage]);
    setQuestion("");
    localStorage.removeItem(CHAT_KEY);
    window.setTimeout(() => composer.current?.focus(), 0);
  }

  async function submit() {
    const submitted = question.trim();
    if (!submitted || loading) return;
    const history = conversationContext(messages);
    const userMessage: ChatMessage = {
      id: newId(),
      role: "user",
      content: submitted,
    };
    setMessages((current) => appendMessages(current, userMessage));
    setQuestion("");
    setLoading(true);
    let establishedSession = sessionReady;
    try {
      const response = await api.ask(
        submitted,
        sessionReady ? undefined : token,
        history,
      );
      establishedSession = aiSession.has();
      setSessionReady(establishedSession);
      const assistantMessage: ChatMessage = {
        id: newId(),
        role: "assistant",
        content: response.kind === "result" ? response.answer : response.message,
        result: response,
      };
      setMessages((current) => appendMessages(current, assistantMessage));
    } catch (caught) {
      if (!aiSession.has()) {
        setSessionReady(false);
        widgetId.current = undefined;
      }
      setMessages((current) =>
        appendMessages(current, {
          id: newId(),
          role: "assistant",
          content:
            caught instanceof Error
              ? caught.message
              : "I could not complete that analysis.",
          error: true,
          retryQuestion: submitted,
        }),
      );
    } finally {
      setLoading(false);
      if (!establishedSession && widgetId.current) {
        window.turnstile?.reset(widgetId.current);
      }
      setToken(undefined);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-white/8 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[#d9ff9f]">
            <Sparkles size={17} />
            <span className="text-xs font-semibold uppercase tracking-[.18em]">
              Logistics conversation
            </span>
          </div>
          <h2 className="text-xl font-semibold tracking-tight">
            Ask, inspect, then follow up.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#93a49e]">
            AI interprets the conversation; validated Python tools calculate every answer.
          </p>
        </div>
        <Button variant="secondary" onClick={newConversation}>
          <MessageSquarePlus size={15} /> New conversation
        </Button>
      </div>

      <div
        role="log"
        aria-label="Logistics AI conversation"
        aria-live="polite"
        className="max-h-[72vh] min-h-[440px] overflow-y-auto bg-[#091411]/50 px-4 py-6 sm:px-6"
      >
        <div className="mx-auto grid max-w-5xl gap-6">
          {messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="flex justify-end gap-3">
                <div className="max-w-[82%] rounded-2xl rounded-tr-md bg-[#b9f55b] px-4 py-3 text-sm leading-6 text-[#07110f] shadow-sm">
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/10 text-[#cbd7d2]">
                  <User size={15} />
                </div>
              </div>
            ) : (
              <div key={message.id} className="flex items-start gap-3">
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#49dcb1]/15 text-[#72ebc8]">
                  <Bot size={16} />
                </div>
                <div className="min-w-0 max-w-[min(100%,920px)] flex-1">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[.14em] text-[#8fa19b]">
                    Logistics AI
                  </p>
                  {message.result?.kind === "result" ? (
                    <ResultPanel result={message.result} />
                  ) : message.result?.kind === "clarification" ? (
                    <div className="grid gap-3 rounded-2xl rounded-tl-md border border-[#f4a261]/20 bg-[#f4a261]/5 p-4">
                      <p className="text-sm leading-6 text-[#f3ddc7]">
                        {message.result.message}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {message.result.suggestions.map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => choosePrompt(suggestion)}
                            className="rounded-full border border-[#f4a261]/20 px-3 py-1.5 text-left text-xs text-[#e6bd92] hover:border-[#f4a261]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div
                      className={`rounded-2xl rounded-tl-md border p-4 text-sm leading-6 ${
                        message.error
                          ? "border-[#df6f74]/25 bg-[#df6f74]/8 text-[#f5b1b4]"
                          : "border-white/8 bg-[#101e1b] text-[#dbe5e1]"
                      }`}
                    >
                      <p>{message.content}</p>
                      {message.id === "welcome" && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {examples.map((example) => (
                            <button
                              key={example}
                              type="button"
                              onClick={() => choosePrompt(example)}
                              className="rounded-full border border-white/10 px-3 py-1.5 text-left text-xs text-[#aebdb8] transition hover:border-[#b9f55b]/40 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                            >
                              {example}
                            </button>
                          ))}
                        </div>
                      )}
                      {message.error && message.retryQuestion && (
                        <button
                          type="button"
                          onClick={() => choosePrompt(message.retryQuestion || "")}
                          className="mt-3 rounded-lg border border-[#df6f74]/25 px-3 py-1.5 text-xs font-semibold hover:bg-[#df6f74]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                        >
                          Put message back in composer
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ),
          )}

          {loading && (
            <div className="flex items-start gap-3" role="status">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#49dcb1]/15 text-[#72ebc8]">
                <Bot size={16} />
              </div>
              <div className="rounded-2xl rounded-tl-md border border-white/8 bg-[#101e1b] px-4 py-3">
                <span className="sr-only">Analyzing your question</span>
                <span className="flex gap-1.5" aria-hidden="true">
                  {[0, 1, 2].map((index) => (
                    <span
                      key={index}
                      className="h-2 w-2 animate-pulse rounded-full bg-[#72ebc8]"
                      style={{ animationDelay: `${index * 160}ms` }}
                    />
                  ))}
                </span>
              </div>
            </div>
          )}
          <div ref={endOfThread} />
        </div>
      </div>

      <div className="border-t border-white/8 bg-[#0d1917] p-4 sm:p-5">
        <form
          className="mx-auto max-w-5xl"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <div className="flex items-end gap-3 rounded-2xl border border-white/10 bg-[#081310] p-2 focus-within:border-[#b9f55b]/40">
            <textarea
              ref={composer}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
              rows={2}
              maxLength={500}
              aria-label="Message Logistics AI"
              className="min-h-14 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-[#7c8d88]"
              placeholder="Ask a question or continue the conversation…"
            />
            <Button
              type="submit"
              disabled={
                loading ||
                !question.trim() ||
                Boolean(siteKey && !sessionReady && !token)
              }
              className="h-11 w-11 rounded-xl p-0"
              aria-label="Send message"
            >
              <ArrowUp size={18} />
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-[11px] text-[#7f918b]">
            <span className="flex items-center gap-1.5">
              <ShieldCheck size={12} />
              {siteKey
                ? sessionReady
                  ? "Security verified for this browser session"
                  : token
                    ? "Turnstile verified · ready to send"
                    : "Completing first-message security check…"
                : "Development mode · Enter to send, Shift+Enter for a new line"}
            </span>
            <span>{question.length}/500</span>
          </div>
          {!sessionReady && <div ref={widget} className="mt-2" />}
        </form>
      </div>
    </Card>
  );
}
