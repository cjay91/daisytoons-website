import type { Instrumentation } from "next";

// Server errors go to Sentry when SENTRY_DSN is set, through Sentry's plain HTTP API (no SDK).
// Every error is also written to the server log either way.

const dsn = process.env.SENTRY_DSN ? new URL(process.env.SENTRY_DSN) : null;

export const onRequestError: Instrumentation.onRequestError = async (error, request, context) => {
  const err = error instanceof Error ? error : new Error(String(error));
  const digest = typeof error === "object" && error !== null && "digest" in error ? String(error.digest) : undefined;
  console.error(`Error on ${request.method} ${request.path} (${context.routePath}):`, err);
  if (!dsn) return;

  const projectId = dsn.pathname.replace(/^\//, "");
  const eventId = crypto.randomUUID().replaceAll("-", "");
  const event = {
    event_id: eventId,
    timestamp: Date.now() / 1000,
    platform: "node",
    level: "error",
    environment: process.env.NODE_ENV,
    server_name: "console",
    transaction: context.routePath,
    // Only the path: query strings can hold order keys.
    tags: { route: context.routePath, router: context.routerKind, render: context.renderSource ?? "", digest: digest ?? "" },
    request: { method: request.method, url: request.path.split("?")[0] },
    exception: { values: [{ type: err.name, value: err.message }] },
    extra: { stack: err.stack },
  };
  const envelope = [
    JSON.stringify({ event_id: eventId, sent_at: new Date().toISOString() }),
    JSON.stringify({ type: "event" }),
    JSON.stringify(event),
  ].join("\n");
  try {
    await fetch(`${dsn.protocol}//${dsn.host}/api/${projectId}/envelope/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-sentry-envelope",
        "X-Sentry-Auth": `Sentry sentry_version=7, sentry_key=${dsn.username}, sentry_client=daisytoons-console/1.0`,
      },
      body: envelope,
      signal: AbortSignal.timeout(3000),
    });
  } catch (sendError) {
    console.error("Could not send the error to Sentry:", sendError);
  }
};
