import "server-only";

import { headers as requestHeaders } from "next/headers";

// Talks to the Daisytoons API from the server. Browsers never call the API directly: login
// and cart tokens stay in httpOnly cookies that page code can't read.

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
  body?: unknown;
  token?: string;
  // Pass the visitor's IP address on, so the API's limits on logins and checkouts count per
  // visitor and not per web server. Only inside a request (Server Actions, dynamic pages).
  forwardIp?: boolean;
  cartToken?: string;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.forwardIp) {
    const incoming = await requestHeaders();
    // Set by the HTTPS proxy in front of the web app.
    const ip = incoming.get("x-forwarded-for")?.split(",")[0]?.trim() || incoming.get("x-real-ip");
    if (ip) headers["X-Forwarded-For"] = ip;
  }
  if (options.cartToken) headers["X-Cart-Token"] = options.cartToken;

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
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

export function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
