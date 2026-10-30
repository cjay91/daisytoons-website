"use server";

import { redirect } from "next/navigation";
import { refresh } from "next/cache";

import { api, ApiError } from "@/lib/api";
import { clearSession, getTokens, liveToken, setCartToken, setLogin } from "@/lib/session";
import type { Address, Cart, CheckoutResult } from "@/lib/types";

export type FormState = { error?: string; fieldErrors?: Record<string, string>; ok?: boolean };

function failure(error: unknown): FormState {
  if (error instanceof ApiError) {
    const fieldErrors: Record<string, string> = {};
    for (const detail of error.details ?? []) {
      const field = detail.field.split(".").at(-1) ?? detail.field;
      fieldErrors[field] = detail.message.replace(/^Value error, /, "");
    }
    return { error: error.message, fieldErrors };
  }
  throw error;
}

function text(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function optional(form: FormData, name: string): string | null {
  return text(form, name) || null;
}

async function cartRequest(path: string, method: string, body?: unknown): Promise<Cart> {
  const { cartToken } = await getTokens();
  const cart = await api<Cart>(path, { method, body, token: await liveToken(), cartToken });
  if (cart.token && cart.token !== cartToken) await setCartToken(cart.token);
  return cart;
}

// Cart

export async function setQuantity(_: FormState, form: FormData): Promise<FormState> {
  const productId = Number(form.get("product_id"));
  const quantity = Number(form.get("quantity"));
  try {
    await cartRequest(`/cart/items/${productId}`, "PUT", { quantity });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

export async function addToCart(_: FormState, form: FormData): Promise<FormState> {
  const productId = Number(form.get("product_id"));
  const adding = Number(form.get("quantity") ?? 1);
  try {
    const cart = await cartRequest("/cart", "POST");
    const current = cart.items.find((item) => item.product_id === productId)?.quantity ?? 0;
    await cartRequest(`/cart/items/${productId}`, "PUT", { quantity: current + adding });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

export async function updateGiftOptions(_: FormState, form: FormData): Promise<FormState> {
  try {
    await cartRequest("/cart", "PATCH", {
      gift_wrap: form.get("gift_wrap") === "on",
      gift_message: text(form, "gift_message"),
    });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

export type GiftMessageState = FormState & { suggestions?: string[] };

export async function suggestGiftMessages(_: GiftMessageState, form: FormData): Promise<GiftMessageState> {
  try {
    const result = await api<{ suggestions: string[] }>("/agents/gift-message", {
      method: "POST",
      forwardIp: true,
      token: await liveToken(),
      body: {
        occasion: text(form, "occasion"),
        recipient: text(form, "recipient"),
        tone: text(form, "tone") || "warm",
        details: text(form, "details"),
      },
    });
    return { ok: true, suggestions: result.suggestions };
  } catch (error) {
    return failure(error);
  }
}

// Checkout

export type CheckoutState = FormState & { result?: CheckoutResult };

export async function placeOrder(_: CheckoutState, form: FormData): Promise<CheckoutState> {
  const { cartToken } = await getTokens();
  try {
    const result = await api<CheckoutResult>("/checkout", {
      method: "POST",
      forwardIp: true,
      token: await liveToken(),
      cartToken,
      body: {
        email: optional(form, "email"),
        customer_name: text(form, "customer_name"),
        phone: text(form, "phone"),
        notes: optional(form, "notes"),
        address: {
          line1: text(form, "line1"),
          line2: optional(form, "line2"),
          city: text(form, "city"),
          district: text(form, "district"),
          postal_code: optional(form, "postal_code"),
        },
      },
    });
    // The browser now posts result.payment to the payment page.
    return { ok: true, result };
  } catch (error) {
    return failure(error);
  }
}

// Accounts

function safeNext(form: FormData): string {
  const next = text(form, "next");
  // Only paths on this site, never another website.
  return next.startsWith("/") && !next.startsWith("//") ? next : "/account";
}

async function startSession(email: string, password: string) {
  const { access_token } = await api<{ access_token: string }>("/auth/login", {
    method: "POST",
    forwardIp: true,
    body: { email, password },
  });
  await setLogin(access_token);
  // Merge any guest cart into the customer's cart now, and keep the customer's cart token.
  const { cartToken } = await getTokens();
  const cart = await api<Cart>("/cart", { token: access_token, cartToken });
  await setCartToken(cart.token);
}

export async function login(_: FormState, form: FormData): Promise<FormState> {
  try {
    await startSession(text(form, "email"), String(form.get("password") ?? ""));
  } catch (error) {
    return failure(error);
  }
  redirect(safeNext(form));
}

export async function register(_: FormState, form: FormData): Promise<FormState> {
  const email = text(form, "email");
  const password = String(form.get("password") ?? "");
  try {
    await api("/auth/register", {
      method: "POST",
      forwardIp: true,
      body: { email, password, full_name: text(form, "full_name"), phone: optional(form, "phone") },
    });
    await startSession(email, password);
  } catch (error) {
    return failure(error);
  }
  redirect(safeNext(form));
}

export async function logout() {
  await clearSession();
  redirect("/");
}

// Addresses

async function requireToken(): Promise<string> {
  const token = await liveToken();
  if (!token) redirect("/login?next=/account/addresses");
  return token;
}

export async function saveAddress(_: FormState, form: FormData): Promise<FormState> {
  const token = await requireToken();
  const id = text(form, "id");
  try {
    await api<Address>(id ? `/me/addresses/${id}` : "/me/addresses", {
      method: id ? "PUT" : "POST",
      token,
      body: {
        label: optional(form, "label"),
        recipient_name: text(form, "recipient_name"),
        phone: optional(form, "phone"),
        line1: text(form, "line1"),
        line2: optional(form, "line2"),
        city: text(form, "city"),
        district: text(form, "district"),
        postal_code: optional(form, "postal_code"),
        is_default: form.get("is_default") === "on",
      },
    });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true };
}

export async function deleteAddress(form: FormData) {
  const token = await requireToken();
  await api(`/me/addresses/${Number(form.get("id"))}`, { method: "DELETE", token });
  refresh();
}
