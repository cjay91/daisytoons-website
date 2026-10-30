import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AGENTS, Outcome, who } from "@/components/AgentRun";
import { Loading } from "@/components/Loading";
import { dateTime, dollars } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { AgentConversation, AgentMessage, AgentToolCall, ContentBlock } from "@/lib/types";

export const metadata: Metadata = { title: "Conversation" };

export default function ConversationPage({ params }: PageProps<"/agents/runs/[id]">) {
  return (
    <div className="flex flex-col gap-4">
      <Link href="/agents" className="text-sm text-muted">
        ← Assistant conversations
      </Link>
      <Suspense fallback={<Loading />}>
        <Conversation params={params} />
      </Suspense>
    </div>
  );
}

async function Conversation({ params }: Pick<PageProps<"/agents/runs/[id]">, "params">) {
  const { id } = await params;
  const conversation = await staffApi<AgentConversation>(`/staff/agent-runs/${Number(id)}`);
  const [first] = conversation.runs;
  const byRun = new Map(conversation.runs.map((run) => [run.id, run]));
  const tokens = conversation.runs.reduce((sum, run) => sum + run.input_tokens + run.output_tokens, 0);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-2xl font-semibold">{AGENTS[first.agent] ?? first.agent}</h1>
        <span className="text-muted">
          {who(first)} · {dateTime(first.started_at)}
        </span>
      </div>
      <section className="grid gap-3 sm:grid-cols-3">
        <Tile label="Cost" value={dollars(conversation.cost)} />
        <Tile label="Messages from the visitor" value={conversation.runs.length} />
        <Tile label="Tokens" value={tokens.toLocaleString()} />
      </section>

      <ol className="flex flex-col gap-3">
        {conversation.messages.map((message) => (
          <Message
            key={message.id}
            message={message}
            calls={conversation.tool_calls.filter((call) => call.run_id === message.run_id)}
            run={byRun.get(message.run_id)!}
            isFirstOfRun={conversation.messages.find((m) => m.run_id === message.run_id)?.id === message.id}
          />
        ))}
      </ol>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function Message({
  message,
  calls,
  run,
  isFirstOfRun,
}: {
  message: AgentMessage;
  calls: AgentToolCall[];
  run: AgentConversation["runs"][number];
  isFirstOfRun: boolean;
}) {
  return (
    <li className="flex flex-col gap-2">
      {isFirstOfRun && (
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
          Run #{run.id} · <Outcome status={run.status} /> · {run.steps} model calls · {dollars(run.cost)}
          {run.error && <span className="text-danger">· {run.error}</span>}
        </p>
      )}
      {message.content.map((block, i) => (
        <Block key={i} block={block} role={message.role} calls={calls} />
      ))}
      {message.role === "assistant" && (
        <p className="text-xs text-muted">
          {message.model} · {message.input_tokens ?? 0} in
          {message.cache_read_tokens ? ` (+${message.cache_read_tokens} cached)` : ""} · {message.output_tokens ?? 0} out ·{" "}
          {message.duration_ms ?? 0} ms · {dollars(message.cost ?? 0)}
        </p>
      )}
    </li>
  );
}

function Block({ block, role, calls }: { block: ContentBlock; role: string; calls: AgentToolCall[] }) {
  if (block.type === "text") {
    return (
      <p
        className={`max-w-3xl rounded-xl p-3 text-sm whitespace-pre-line ${role === "user" ? "self-start bg-accent-soft" : "card self-start"}`}
      >
        <span className="mb-1 block text-xs font-semibold text-muted">{role === "user" ? "Visitor" : "Assistant"}</span>
        {block.text}
      </p>
    );
  }
  if (block.type === "tool_use") {
    const call = calls.find((c) => c.tool_use_id === block.id);
    return (
      <details className="card max-w-3xl p-3 text-sm">
        <summary className="cursor-pointer">
          <span className="font-mono">{block.name}</span>
          {call?.error ? <span className="ml-2 text-danger">failed: {call.error}</span> : <span className="ml-2 text-muted">ok</span>}
          {call && <span className="ml-2 text-xs text-muted">{call.duration_ms} ms</span>}
        </summary>
        <p className="mt-2 text-xs font-semibold text-muted">Input</p>
        <pre className="overflow-x-auto text-xs">{JSON.stringify(block.input, null, 2)}</pre>
        {call && !call.error && (
          <>
            <p className="mt-2 text-xs font-semibold text-muted">Result</p>
            <pre className="max-h-64 overflow-auto text-xs">{JSON.stringify(call.output, null, 2)}</pre>
          </>
        )}
      </details>
    );
  }
  // Tool results are shown with their call; thinking isn't kept in a readable form.
  return null;
}
