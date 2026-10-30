import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { AGENTS, Outcome, who } from "@/components/AgentRun";
import { Loading } from "@/components/Loading";
import { query } from "@/lib/api";
import { dateTime, dollars } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { AgentRunList, AgentTotals } from "@/lib/types";

export const metadata: Metadata = { title: "Assistant" };


export default function AgentsPage({ searchParams }: PageProps<"/agents">) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Assistant conversations</h1>
      <Suspense fallback={<Loading />}>
        <Runs searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

function one(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

async function Runs({ searchParams }: Pick<PageProps<"/agents">, "searchParams">) {
  const params = await searchParams;
  const agent = one(params.agent);
  const status = one(params.status);
  const before = one(params.before);
  const list = await staffApi<AgentRunList>(`/staff/agent-runs${query({ agent, status, before })}`);
  const last = list.runs.at(-1);

  return (
    <>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Totals label="Today" totals={list.today} />
        <Totals label="Last 7 days" totals={list.last_7_days} />
        {Object.entries(list.by_agent).map(([name, totals]) => (
          <Totals key={name} label={`${AGENTS[name] ?? name}, 7 days`} totals={totals} />
        ))}
      </section>

      <Form action="/agents" className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor="agent" className="label">
            Agent
          </label>
          <select id="agent" name="agent" defaultValue={agent ?? ""} className="input">
            <option value="">All</option>
            {Object.entries(AGENTS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="status" className="label">
            Outcome
          </label>
          <select id="status" name="status" defaultValue={status ?? ""} className="input">
            <option value="">All</option>
            <option value="finished">Finished</option>
            <option value="waiting">Waiting for approval</option>
            <option value="stopped">Stopped at a limit</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <button className="btn-outline">Show</button>
      </Form>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr className="border-b border-line">
              <th className="p-3 font-medium">When</th>
              <th className="p-3 font-medium">Agent</th>
              <th className="p-3 font-medium">Who</th>
              <th className="p-3 font-medium">Message</th>
              <th className="p-3 font-medium">Outcome</th>
              <th className="p-3 text-right font-medium">Tokens</th>
              <th className="p-3 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {list.runs.map((run) => (
              <tr key={run.id} className="border-b border-line last:border-0 hover:bg-accent-soft/40">
                <td className="p-3 whitespace-nowrap">
                  <Link href={`/agents/runs/${run.id}`} className="hover:underline">
                    {dateTime(run.started_at)}
                  </Link>
                </td>
                <td className="p-3">{AGENTS[run.agent] ?? run.agent}</td>
                <td className="p-3">{who(run)}</td>
                <td className="max-w-sm truncate p-3">
                  <Link href={`/agents/runs/${run.id}`} className="hover:underline">
                    {run.input}
                  </Link>
                </td>
                <td className="p-3">
                  <Outcome status={run.status} />
                </td>
                <td className="p-3 text-right tabular-nums">{(run.input_tokens + run.output_tokens).toLocaleString()}</td>
                <td className="p-3 text-right tabular-nums">{dollars(run.cost)}</td>
              </tr>
            ))}
            {list.runs.length === 0 && (
              <tr>
                <td colSpan={7} className="p-6 text-center text-muted">
                  No conversations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {last && list.runs.length === 50 && (
        <Link href={`/agents${query({ agent, status, before: last.id })}`} className="btn-outline self-start">
          Older
        </Link>
      )}
    </>
  );
}

function Totals({ label, totals }: { label: string; totals: AgentTotals }) {
  return (
    <div className="card p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{dollars(totals.cost)}</p>
      <p className="text-xs text-muted">
        {totals.runs} {totals.runs === 1 ? "run" : "runs"} · {totals.tokens.toLocaleString()} tokens
        {totals.failed > 0 && <span className="text-danger"> · {totals.failed} failed</span>}
      </p>
    </div>
  );
}
