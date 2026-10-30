# Part 8 spec: agent harness

Goal: our own agent framework, in `backend/app/agents/`, before any agent goes live.

Done when: a test agent passes its eval suite in CI, and a tool marked `approve` never runs
without an approval. Both are checked on every push without calling the real model: evals
run against a scripted model, plus an optional live run when `ANTHROPIC_API_KEY` is set.

No agent talks to customers or changes the shop in this part. Parts 10 and 11 add the real
agents on top of this.

## Pieces

| File | What it is |
| --- | --- |
| `agents/core.py` | The agent loop (`agent_core.py` in the plan): send the conversation, run the tools the model asks for, repeat until it answers or hits a limit. `run_stream()` yields events; `run()` collects them. |
| `agents/tools.py` | The tool registry: a typed Pydantic input, a risk level, the permission it needs, who it's offered to, and a function that calls a service |
| `agents/context.py` | Who the agent is acting for: a customer (or guest) or a staff member |
| `agents/model.py` | The Claude API through the Anthropic SDK, a scripted model for tests and evals, and the price table for costs |
| `agents/evals.py` | The eval runner and the test agent's suite |
| `agents/test_agent.py` | `stock_helper`, a small staff agent that proves the harness: it finds products and reads stock (`auto`), records a shelf (`notify`), and asks to change a reorder point (`approve`) |
| `agents/catalog.py` | Every agent by name |
| `services/approvals.py` | Approving (optionally with an edited input) or rejecting a request |

Tools call the same `services/` functions as the API and console, and never use the database
directly. Permissions are checked in the tool runner, in code, never in the prompt. A tool a run
can't use isn't offered to the model, and if the model calls it anyway, it gets an error back.

The model is Claude Opus 5.5 by default (`AGENT_MODEL`), with adaptive thinking, an effort level
per agent, prompt caching, and the API's automatic retry on another model if a request is
declined. Every call streams.

## Risk levels

| Level | What happens |
| --- | --- |
| `auto` | Runs straight away. Read-only lookups. |
| `notify` | Runs straight away and is written to the audit log for staff to see. |
| `approve` | Doesn't run. It creates an approval request with the exact input and the agent's stated reason, and the agent is told it's waiting. The tool runs only when a staff member with the tool's permission approves it, as that staff member, with that input (or their edit of it), and only once. Requests expire after 7 days. |

A run that ends with requests still pending is marked "waiting", and "finished" once they're
all decided. The model isn't called again after a decision; Part 11 can tell the agent the
outcome if that's useful.

## Tables

- `agent_runs`: the agent, who it acted for, status (running, finished, waiting for approval, stopped at a limit, failed), steps, input and output tokens, cost, start and end times.
- `agent_messages`: the conversation, in order, so a chat can carry on in a later run with the same `conversation_id`. Each assistant message also traces its model call: model, stop reason, tokens (including cache), cost and time.
- `agent_tool_calls`: each tool call in a run: tool, input, output or error, risk level, timing.
- `approval_requests`: the tool, its input, the run that asked, the reason the agent gave, status (pending, approved, rejected, expired), who decided and when, and the result once it ran.
- `audit_log`: every write by an agent (`notify` and approved `approve` tools), with who it acted for and who approved it.

## Limits

Set per agent, with defaults: 10 steps, 50,000 tokens and US$0.50 per run. A run that hits a
limit stops, is marked "stopped at a limit", and returns a polite fallback answer. Cost uses a
price table per model in `agents/model.py`.

## Streaming

`run_stream()` yields events (text as it arrives, tool started, tool finished, approval
requested, done), so Part 10's chat widget can show the answer as it's written. There's no
HTTP endpoint for it yet; Part 10 adds one.

## Evals

Each scenario gives the user's message, who the agent acts for, and a scripted model's
replies or a live model, then checks the tool calls made, approvals created, and the final
answer. The test agent's suite covers:

- Answering a stock question with the right lookup.
- An `approve` tool creates a request and doesn't run, then runs once when approved, and not at all when rejected.
- A customer-scoped run can't call a staff-only tool.
- Limits stop a run that loops.
- A notify tool runs and is written to the audit log.
- A tool error is reported to the model rather than crashing the run.

Every scenario runs in a transaction that's rolled back, so evals never change the shop.
CI runs them with the scripted model as part of the backend tests.
`python -m app.cli run-evals [agent] [--live]` runs them by hand; `--live` uses the real model
and needs `ANTHROPIC_API_KEY`.

## Left for later

- Console pages for approvals, audit log and traces, and pausing an agent: Part 11.
- Background triggers (`order.paid` and others), and a system actor for agents that run on their own: Part 11.
- Product and policy search: Part 9.
