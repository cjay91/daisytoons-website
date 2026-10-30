"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState } from "react";

import type { Contact } from "@/lib/types";

type AgentName = "gift_concierge" | "support";
type Message = { role: "user" | "assistant"; text: string; error?: boolean };
type Conversation = { id: string | null; messages: Message[] };

const TABS: { agent: AgentName; label: string; hello: string; placeholder: string }[] = [
  {
    agent: "gift_concierge",
    label: "Gift ideas",
    hello: "Hi! Tell me who the gift is for, the occasion and your budget, and I'll suggest something.",
    placeholder: "A birthday gift for my sister, under Rs 5,000",
  },
  {
    agent: "support",
    label: "Order help",
    hello: "Hi! I can check an order, answer delivery questions or start a return. What do you need?",
    placeholder: "Where is my order?",
  },
];

const STORAGE_KEY = "dt_chat";
const EMPTY: Record<AgentName, Conversation> = {
  gift_concierge: { id: null, messages: [] },
  support: { id: null, messages: [] },
};

// What a tool is doing, shown while the reply is on its way.
const TOOL_STATUS: Record<string, string> = {
  search_products: "Looking through the shop…",
  search_knowledge: "Checking our policies…",
  add_to_cart: "Adding to your cart…",
  get_my_orders: "Looking up your orders…",
  get_order_status: "Looking up the order…",
  start_return: "Starting the return…",
  contact_a_person: "Finding the best way to reach us…",
};

export function ChatWidget({ contact }: { contact: Contact }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<AgentName>("gift_concierge");
  const [conversations, setConversations] = useState(EMPTY);
  const [busy, setBusy] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const log = useRef<HTMLDivElement>(null);
  const restored = useRef(false);

  // The conversation survives page changes and reloads within the tab, not beyond.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sessionStorage is only readable after hydration
      if (saved) setConversations({ ...EMPTY, ...JSON.parse(saved) });
    } catch {}
    restored.current = true;
  }, []);
  useEffect(() => {
    if (!restored.current) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch {}
  }, [conversations]);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [conversations, busy, tab, open]);

  const current = TABS.find((t) => t.agent === tab)!;
  const conversation = conversations[tab];

  function update(agent: AgentName, change: (c: Conversation) => Conversation) {
    setConversations((all) => ({ ...all, [agent]: change(all[agent]) }));
  }

  function setLastReply(agent: AgentName, change: (m: Message) => Message) {
    update(agent, (c) => ({ ...c, messages: [...c.messages.slice(0, -1), change(c.messages.at(-1)!)] }));
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || busy) return;
    const agent = tab;
    setDraft("");
    setBusy("Thinking…");
    update(agent, (c) => ({
      ...c,
      messages: [...c.messages, { role: "user", text: message }, { role: "assistant", text: "" }],
    }));
    let cartChanged = false;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent, message, conversation_id: conversations[agent].id }),
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.error?.message ?? "The assistant isn't available right now.");
      }
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      let streamed = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === "start") {
            update(agent, (c) => ({ ...c, id: data.conversation_id }));
          } else if (data.type === "text") {
            // Text before a tool call is the model thinking aloud; keep only the latest part.
            streamed += data.text;
            setBusy(null);
            setLastReply(agent, (m) => ({ ...m, text: streamed }));
          } else if (data.type === "tool") {
            streamed = "";
            setBusy(TOOL_STATUS[data.tool] ?? "Working on it…");
            if (data.tool === "add_to_cart" && data.ok) cartChanged = true;
          } else if (data.type === "done") {
            setLastReply(agent, (m) => ({ ...m, text: data.text, error: data.status === "failed" }));
          }
        }
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : "Something went wrong.";
      setLastReply(agent, (m) => ({ ...m, text, error: true }));
    } finally {
      setBusy(null);
      if (cartChanged) router.refresh();
    }
  }

  function restart() {
    update(tab, () => ({ id: null, messages: [] }));
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="btn fixed right-4 bottom-4 z-30 rounded-full px-5 py-3 shadow-lg print:hidden"
        aria-haspopup="dialog"
      >
        <span aria-hidden>✿</span> Need help?
      </button>
    );
  }

  return (
    <section
      role="dialog"
      aria-label="Shop assistant"
      className="card fixed inset-x-2 bottom-2 z-30 flex max-h-[80vh] flex-col overflow-hidden shadow-xl sm:inset-x-auto sm:right-4 sm:bottom-4 sm:w-96 print:hidden"
    >
      <header className="flex items-center gap-1 border-b border-line p-2">
        {TABS.map((t) => (
          <button
            key={t.agent}
            onClick={() => setTab(t.agent)}
            aria-pressed={t.agent === tab}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${t.agent === tab ? "bg-accent-soft" : "text-muted hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
        <button onClick={restart} className="ml-auto px-2 text-xs text-muted hover:text-foreground" disabled={!!busy}>
          Start over
        </button>
        <button onClick={() => setOpen(false)} className="px-2 text-lg leading-none text-muted hover:text-foreground" aria-label="Close">
          ×
        </button>
      </header>

      <div ref={log} className="flex min-h-48 flex-1 flex-col gap-3 overflow-y-auto p-3 text-sm" aria-live="polite">
        <Bubble message={{ role: "assistant", text: current.hello }} />
        {conversation.messages.map((message, i) =>
          message.text ? <Bubble key={i} message={message} /> : null,
        )}
        {busy && <p className="text-muted italic">{busy}</p>}
      </div>

      <form onSubmit={send} className="flex gap-2 border-t border-line p-2">
        <label htmlFor="chat-message" className="sr-only">
          Your message
        </label>
        <input
          id="chat-message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={2000}
          placeholder={current.placeholder}
          className="input flex-1 py-2"
          autoComplete="off"
        />
        <button className="btn px-4 py-2" disabled={!!busy || !draft.trim()}>
          Send
        </button>
      </form>
      <p className="border-t border-line px-3 py-2 text-xs text-muted">
        Prefer a person?{" "}
        <a href={contact.email_link} className="underline hover:text-brand">
          Email {contact.email}
        </a>
        {contact.whatsapp_link && (
          <>
            {" or "}
            <a href={contact.whatsapp_link} target="_blank" rel="noopener noreferrer" className="underline hover:text-brand">
              WhatsApp us
            </a>
          </>
        )}
        . The assistant is AI and can make mistakes; it never sees your payment details.
      </p>
    </section>
  );
}

function Bubble({ message }: { message: Message }) {
  const mine = message.role === "user";
  return (
    <p
      className={`max-w-[85%] rounded-2xl px-3 py-2 whitespace-pre-line ${
        mine ? "self-end bg-brand text-white" : message.error ? "bg-accent-soft text-danger" : "bg-accent-soft"
      }`}
    >
      {mine ? message.text : <Linked text={message.text} />}
    </p>
  );
}

// Site paths, web links and email addresses in a reply become links. Only paths on this site
// open in place; anything else opens in a new tab.
const LINK = /(\/(?:products|shop|cart|occasions|for|shipping|returns|privacy|terms|account|order)\b(?:[\w\-/?=&.]*[\w/])?|https?:\/\/[^\s)]+[^\s).,]|[\w.+-]+@[\w-]+\.[\w.]+\w)/g;

function Linked({ text }: { text: string }) {
  const parts = text.split(LINK);
  return parts.map((part, i) => {
    if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;
    if (part.startsWith("/")) {
      return (
        <Link key={i} href={part} className="underline hover:text-brand">
          {part}
        </Link>
      );
    }
    const href = part.includes("@") && !part.startsWith("http") ? `mailto:${part}` : part;
    return (
      <a key={i} href={href} target="_blank" rel="noopener noreferrer" className="underline hover:text-brand">
        {part}
      </a>
    );
  });
}
