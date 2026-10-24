import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { api, ApiError } from "./api";
import type { Cart, Customer } from "./types";

const LOGIN_COOKIE = "dt_login";
const CART_COOKIE = "dt_cart";
// Matches the API's login token lifetime (JWT_EXPIRE_MINUTES).
const LOGIN_MAX_AGE = 60 * 60;
const CART_MAX_AGE = 60 * 60 * 24 * 60;

const cookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export async function getTokens() {
  const store = await cookies();
  return {
    token: store.get(LOGIN_COOKIE)?.value,
    cartToken: store.get(CART_COOKIE)?.value,
  };
}

// The cookie setters only work inside Server Actions and Route Handlers.
export async function setLogin(token: string) {
  (await cookies()).set(LOGIN_COOKIE, token, { ...cookieOptions, maxAge: LOGIN_MAX_AGE });
}

export async function setCartToken(token: string | null) {
  const store = await cookies();
  if (token) store.set(CART_COOKIE, token, { ...cookieOptions, maxAge: CART_MAX_AGE });
  else store.delete(CART_COOKIE);
}

export async function clearSession() {
  const store = await cookies();
  store.delete(LOGIN_COOKIE);
  store.delete(CART_COOKIE);
}

/** The logged-in customer, or null for a guest or an expired login. Once per request. */
export const getCustomer = cache(async (): Promise<Customer | null> => {
  const { token } = await getTokens();
  if (!token) return null;
  try {
    return await api<Customer>("/me", { token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
});

/** A login token that still works, or undefined. An expired login is treated as a guest. */
export async function liveToken(): Promise<string | undefined> {
  const { token } = await getTokens();
  return token && (await getCustomer()) ? token : undefined;
}

export const getCart = cache(async (): Promise<Cart> => {
  const { cartToken } = await getTokens();
  return api<Cart>("/cart", { token: await liveToken(), cartToken });
});
