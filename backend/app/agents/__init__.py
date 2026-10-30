"""The agent harness (Part 8): our own agent loop, tools, approvals, tracing and evals.

Agents never touch the database directly. Tools call the same services as the API and console,
and permissions and approvals are enforced here in code, never in a prompt.
"""
