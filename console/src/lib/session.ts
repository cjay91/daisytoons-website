import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { api, ApiError } from "./api";
import type { Staff } from "./types";

const LOGIN_COOKIE = "dt_staff";
// Holds the password-checked half of a login while the person types their code.
const CHALLENGE_COOKIE = "dt_staff_2fa";
// Matches the API's login token lifetime (JWT_EXPIRE_MINUTES).
const LOGIN_MAX_AGE = 60 * 60;

export async function setLogin(token: string) {
  (await cookies()).set(LOGIN_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: LOGIN_MAX_AGE,
  });
}

export async function clearLogin() {
  (await cookies()).delete(LOGIN_COOKIE);
}

export async function setChallenge(token: string | null) {
  const store = await cookies();
  if (!token) store.delete(CHALLENGE_COOKIE);
  else
    store.set(CHALLENGE_COOKIE, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 5 * 60,
    });
}

export async function getChallenge(): Promise<string | undefined> {
  return (await cookies()).get(CHALLENGE_COOKIE)?.value;
}

/** The logged-in staff member, or null. Once per request. */
export const getStaff = cache(async (): Promise<Staff | null> => {
  const token = (await cookies()).get(LOGIN_COOKIE)?.value;
  if (!token) return null;
  try {
    return await api<Staff>("/staff/me", { token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
});

/** Call the API as the logged-in staff member. No login, or an expired one, goes to /login. */
export async function staffApi<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = (await cookies()).get(LOGIN_COOKIE)?.value;
  if (!token) redirect("/login");
  try {
    return await api<T>(path, { ...options, token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    if (error instanceof ApiError && error.code === "two_factor_setup_required") redirect("/security");
    throw error;
  }
}

export async function requireStaff(): Promise<Staff> {
  const staff = await getStaff();
  if (!staff) redirect("/login");
  return staff;
}
