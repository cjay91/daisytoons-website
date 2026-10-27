import "server-only";

import { headers as requestHeaders } from "next/headers";

// Talks to the Daisytoons API from the server. The browser never sees the staff login token:
// it stays in an httpOnly cookie.

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { field: string; message: string }[],
  ) {
    super(message);
  }
}

type Options = {
  method?: string;
  // JSON, or FormData for file uploads.
  body?: unknown;
  token?: string;
  // Pass the visitor's IP address on, so the API's limits on logins and checkouts count per
  // visitor and not per web server. Only inside a request (Server Actions, dynamic pages).
  forwardIp?: boolean;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.forwardIp) {
    const incoming = await requestHeaders();
    // Set by the HTTPS proxy in front of the web app.
    const ip = incoming.get("x-forwarded-for")?.split(",")[0]?.trim() || incoming.get("x-real-ip");
    if (ip) headers["X-Forwarded-For"] = ip;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.error ?? {};
    throw new ApiError(
      response.status,
      error.code ?? "error",
      error.message ?? "Something went wrong. Please try again.",
      error.details,
    );
  }
  return data as T;
}

export function query(params: Record<string, string | number | boolean | string[] | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else if (value !== undefined && value !== null && value !== "" && value !== false) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
