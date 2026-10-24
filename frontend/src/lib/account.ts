import "server-only";

import { redirect } from "next/navigation";

import { liveToken } from "./session";

/** The login token, or a redirect to the login page that comes back here afterwards. */
export async function requireLogin(returnTo: string): Promise<string> {
  const token = await liveToken();
  if (!token) redirect(`/login?next=${encodeURIComponent(returnTo)}`);
  return token;
}
