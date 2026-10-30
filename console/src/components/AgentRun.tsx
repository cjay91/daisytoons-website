import type { AgentRun } from "@/lib/types";

export const AGENTS: Record<string, string> = {
  gift_concierge: "Gift concierge",
  support: "Customer support",
  gift_message: "Gift messages",
  stock_helper: "Stock helper",
};

export function who(run: AgentRun): string {
  if (run.staff_id) return `Staff #${run.staff_id}`;
  return run.customer_id ? `Customer #${run.customer_id}` : "Guest";
}

export function Outcome({ status }: { status: AgentRun["status"] }) {
  const style = status === "failed" || status === "stopped" ? "bg-danger-soft text-danger" : "bg-accent-soft";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${style}`}>{status}</span>;
}
