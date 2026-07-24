import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Check,
  History,
  MessageSquarePlus,
  Pencil,
  Sparkles,
  Trash2,
  User,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import type {
  AskResult,
  ConversationSummary,
  ConversationTurn,
  StoredMessage,
} from "../lib/types";
import { Button, Card, Skeleton } from "./ui";
import { ResultPanel } from "./ResultPanel";

const examples = [
  "Show delayed orders by week for the last 3 months",
  "Which carrier has the highest delay rate?",
  "Why are deliveries delayed?",
  "Predict demand for PAPER-0197 for the next 4 months",
  "How much inventory should I plan?",
];
const MAX_CONTEXT_MESSAGES = 8;

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

function fromStoredMessage(message: StoredMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    result: message.result || undefined,
  };
}

function appendMessages(current: ChatMessage[], ...next: ChatMessage[]) {
  return [...current, ...next];
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
  return turns.slice(-MAX_CONTEXT_MESSAGES);
}

export function AIPanel() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const composer = useRef<HTMLTextAreaElement>(null);
  const endOfThread = useRef<HTMLDivElement>(null);

  async function refreshConversations() {
    try {
      const response = await api.conversations();
      setConversations(response.conversations);
      setHistoryError("");
    } catch (caught) {
      setHistoryError(
        caught instanceof Error ? caught.message : "Unable to load conversation history.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    void refreshConversations();
  }, []);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  function choosePrompt(prompt: string) {
    setQuestion(prompt);
    window.setTimeout(() => composer.current?.focus(), 0);
  }

  function newConversation() {
    setActiveId(null);
    setMessages([welcomeMessage]);
    setQuestion("");
    setEditingId(null);
    window.setTimeout(() => composer.current?.focus(), 0);
  }

  async function openConversation(id: string) {
    if (loading || id === activeId) return;
    setHistoryLoading(true);
    try {
      const conversation = await api.conversation(id);
      setActiveId(id);
      setMessages([
        welcomeMessage,
        ...conversation.messages.map(fromStoredMessage),
      ]);
      setHistoryError("");
    } catch (caught) {
      setHistoryError(
        caught instanceof Error ? caught.message : "Unable to open conversation.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  function beginRename(conversation: ConversationSummary) {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
  }

  async function saveRename(id: string) {
    const title = editingTitle.trim();
    if (!title) return;
    try {
      await api.renameConversation(id, title);
      setEditingId(null);
      await refreshConversations();
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Unable to rename conversation.");
    }
  }

  async function deleteConversation(id: string) {
    try {
      await api.deleteConversation(id);
      if (activeId === id) newConversation();
      await refreshConversations();
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Unable to delete conversation.");
    }
  }

  async function submit() {
    const submitted = question.trim();
    if (!submitted || loading) return;
    const history = conversationContext(messages);
    setMessages((current) =>
      appendMessages(current, {
        id: newId(),
        role: "user",
        content: submitted,
      }),
    );
    setQuestion("");
    setLoading(true);
    try {
      const response = await api.ask(
        submitted,
        undefined,
        history,
        activeId || undefined,
      );
      const conversationId =
        typeof response.meta.conversation_id === "string"
          ? response.meta.conversation_id
          : activeId;
      if (conversationId) setActiveId(conversationId);
      setMessages((current) =>
        appendMessages(current, {
          id: newId(),
          role: "assistant",
          content: response.kind === "result" ? response.answer : response.message,
          result: response,
        }),
      );
      await refreshConversations();
    } catch (caught) {
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
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="grid lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-b border-white/8 bg-[#091411] lg:min-h-[720px] lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between border-b border-white/8 p-4">
            <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-[#9fb0aa]">
              <History size={15} /> History
            </span>
            <Button
              variant="secondary"
              onClick={newConversation}
              className="h-9 px-3"
              aria-label="New conversation"
            >
              <MessageSquarePlus size={15} /> New
            </Button>
          </div>
          <div className="max-h-56 overflow-y-auto p-2 lg:max-h-[650px]">
            {historyLoading && conversations.length === 0 ? (
              <div className="grid gap-2 p-2">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="p-4 text-xs leading-5 text-[#82948e]">
                Your saved conversations will appear here.
              </p>
            ) : (
              <ul className="grid gap-1">
                {conversations.map((conversation) => (
                  <li
                    key={conversation.id}
                    className={`group rounded-xl border ${
                      activeId === conversation.id
                        ? "border-[#b9f55b]/25 bg-[#b9f55b]/8"
                        : "border-transparent hover:bg-white/[.035]"
                    }`}
                  >
                    {editingId === conversation.id ? (
                      <form
                        className="flex items-center gap-1 p-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void saveRename(conversation.id);
                        }}
                      >
                        <input
                          autoFocus
                          value={editingTitle}
                          maxLength={120}
                          aria-label="Conversation title"
                          onChange={(event) => setEditingTitle(event.target.value)}
                          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#07110f] px-2 py-1.5 text-xs outline-none focus:border-[#b9f55b]/50"
                        />
                        <button
                          type="submit"
                          aria-label="Save conversation title"
                          className="rounded-md p-1.5 text-[#b9f55b] hover:bg-white/5"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          type="button"
                          aria-label="Cancel renaming"
                          onClick={() => setEditingId(null)}
                          className="rounded-md p-1.5 text-[#93a49e] hover:bg-white/5"
                        >
                          <X size={14} />
                        </button>
                      </form>
                    ) : (
                      <div className="flex items-center gap-1 p-1">
                        <button
                          type="button"
                          onClick={() => void openConversation(conversation.id)}
                          className="min-w-0 flex-1 rounded-lg px-2 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b9f55b]"
                        >
                          <span className="block truncate text-xs font-medium text-[#dbe5e1]">
                            {conversation.title}
                          </span>
                          <span className="mt-1 block text-[10px] text-[#71837d]">
                            {conversation.message_count} messages
                          </span>
                        </button>
                        <button
                          type="button"
                          aria-label={`Rename ${conversation.title}`}
                          onClick={() => beginRename(conversation)}
                          className="rounded-md p-1.5 text-[#71837d] opacity-70 hover:bg-white/5 hover:text-white focus:opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          type="button"
                          aria-label={`Delete ${conversation.title}`}
                          onClick={() => void deleteConversation(conversation.id)}
                          className="rounded-md p-1.5 text-[#71837d] opacity-70 hover:bg-[#df6f74]/10 hover:text-[#f5b1b4] focus:opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {historyError && (
              <div className="m-2 rounded-lg border border-[#df6f74]/20 bg-[#df6f74]/8 p-3 text-xs text-[#f5b1b4]">
                <p>{historyError}</p>
                <button
                  type="button"
                  onClick={() => void refreshConversations()}
                  className="mt-2 font-semibold underline"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        </aside>

        <div className="min-w-0">
          <div className="border-b border-white/8 p-5 sm:p-6">
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
              Conversations are saved to your account. AI interprets context; validated
              Python tools calculate every answer.
            </p>
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
                  disabled={loading || !question.trim()}
                  className="h-11 w-11 rounded-xl p-0"
                  aria-label="Send message"
                >
                  <ArrowUp size={18} />
                </Button>
              </div>
              <div className="mt-2 flex items-center justify-between gap-2 px-1 text-[11px] text-[#7f918b]">
                <span>Saved history · Enter to send · Shift+Enter for a new line</span>
                <span>{question.length}/500</span>
              </div>
            </form>
          </div>
        </div>
      </div>
    </Card>
  );
}
