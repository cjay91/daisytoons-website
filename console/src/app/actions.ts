"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import { clearLogin, setLogin, staffApi } from "@/lib/session";
import type { Product, PurchaseOrder, Supplier } from "@/lib/types";

export type FormState = { error?: string; fieldErrors?: Record<string, string>; ok?: boolean; message?: string };

function failure(error: unknown): FormState {
  if (error instanceof ApiError) {
    const fieldErrors: Record<string, string> = {};
    for (const detail of error.details ?? []) {
      const field = detail.field.split(".").at(-1) ?? detail.field;
      fieldErrors[field] = detail.message.replace(/^Value error, /, "");
    }
    const fields = Object.entries(fieldErrors).map(([field, message]) => `${field}: ${message}`);
    return { error: fields.length ? `${error.message} ${fields.join("; ")}` : error.message, fieldErrors };
  }
  throw error;
}

function text(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function optional(form: FormData, name: string): string | null {
  return text(form, name) || null;
}

/** Run an API call; on success refresh the page, on failure show the API's message. */
async function attempt(call: () => Promise<unknown>, message?: string): Promise<FormState> {
  try {
    await call();
  } catch (error) {
    return failure(error);
  }
  refresh();
  return { ok: true, message };
}

// Login

export async function login(_: FormState, form: FormData): Promise<FormState> {
  try {
    const { access_token } = await api<{ access_token: string }>("/staff/auth/login", {
      method: "POST",
      body: { email: text(form, "email"), password: String(form.get("password") ?? "") },
    });
    await setLogin(access_token);
  } catch (error) {
    return failure(error);
  }
  const next = text(form, "next");
  redirect(next.startsWith("/") && !next.startsWith("//") ? next : "/");
}

export async function logout() {
  await clearLogin();
  redirect("/login");
}

// Orders

function orderPath(form: FormData, action: string): string {
  return `/staff/orders/${encodeURIComponent(text(form, "order_number"))}/${action}`;
}

export async function packOrder(_: FormState, form: FormData): Promise<FormState> {
  return attempt(() => staffApi(orderPath(form, "pack"), { method: "POST" }));
}

export async function packSelected(form: FormData) {
  const numbers = form.getAll("order").map(String);
  if (numbers.length) {
    await staffApi("/staff/orders/pack", { method: "POST", body: { order_numbers: numbers } });
  }
  redirect("/packing");
}

export async function shipOrder(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () =>
      staffApi(orderPath(form, "ship"), {
        method: "POST",
        body: {
          courier: text(form, "courier"),
          tracking_number: text(form, "tracking_number"),
          tracking_url: optional(form, "tracking_url"),
        },
      }),
    "Shipped. The customer has been emailed the tracking number.",
  );
}

export async function resendTracking(_: FormState, form: FormData): Promise<FormState> {
  return attempt(() => staffApi(orderPath(form, "resend-tracking"), { method: "POST" }), "Tracking email sent again.");
}

export async function markDelivered(_: FormState, form: FormData): Promise<FormState> {
  return attempt(() => staffApi(orderPath(form, "deliver"), { method: "POST" }));
}

export async function cancelOrder(_: FormState, form: FormData): Promise<FormState> {
  return attempt(() =>
    staffApi(orderPath(form, "cancel"), {
      method: "POST",
      body: { reason: text(form, "reason"), refund_reference: optional(form, "refund_reference") },
    }),
  );
}

export async function refundOrder(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () =>
      staffApi(orderPath(form, "refunds"), {
        method: "POST",
        body: {
          amount: text(form, "amount"),
          reason: text(form, "reason"),
          reference: optional(form, "reference"),
          restock: form.get("restock") === "on",
        },
      }),
    "Refund recorded.",
  );
}

export async function resolveAttention(_: FormState, form: FormData): Promise<FormState> {
  return attempt(() => staffApi(orderPath(form, "resolve-attention"), { method: "POST" }));
}

// Products

function productBody(form: FormData) {
  return {
    name: text(form, "name"),
    slug: text(form, "slug"),
    description: text(form, "description"),
    price: text(form, "price"),
    is_active: form.get("is_active") === "on",
  };
}

export async function createProduct(_: FormState, form: FormData): Promise<FormState> {
  let product: Product;
  try {
    product = await staffApi<Product>("/staff/products", {
      method: "POST",
      body: { ...productBody(form), sku: text(form, "sku") },
    });
  } catch (error) {
    return failure(error);
  }
  redirect(`/products/${product.id}`);
}

export async function updateProduct(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () => staffApi(`/staff/products/${text(form, "product_id")}`, { method: "PATCH", body: productBody(form) }),
    "Saved.",
  );
}

export async function setProductTags(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () =>
      staffApi(`/staff/products/${text(form, "product_id")}/tags`, {
        method: "PUT",
        body: { occasions: form.getAll("occasions").map(String), recipients: form.getAll("recipients").map(String) },
      }),
    "Tags saved.",
  );
}

export async function uploadImage(_: FormState, form: FormData): Promise<FormState> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Choose a photo to upload." };
  const upload = new FormData();
  upload.set("file", file, file.name);
  upload.set("alt_text", text(form, "alt_text"));
  return attempt(
    () => staffApi(`/staff/products/${text(form, "product_id")}/images`, { method: "POST", body: upload }),
    "Photo added.",
  );
}

export async function updateImage(_: FormState, form: FormData): Promise<FormState> {
  const path = `/staff/products/${text(form, "product_id")}/images/${text(form, "image_id")}`;
  if (form.get("intent") === "delete") return attempt(() => staffApi(path, { method: "DELETE" }));
  const body: Record<string, unknown> = { alt_text: text(form, "alt_text") };
  if (form.get("intent") === "first") body.position = 0;
  return attempt(() => staffApi(path, { method: "PATCH", body }));
}

export async function updateInventory(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () =>
      staffApi(`/staff/products/${text(form, "product_id")}/inventory`, {
        method: "PATCH",
        body: { reorder_point: Number(text(form, "reorder_point") || 0), bin_location: text(form, "bin_location") },
      }),
    "Saved.",
  );
}

export async function adjustStock(_: FormState, form: FormData): Promise<FormState> {
  const amount = text(form, "amount");
  const isCount = form.get("kind") === "count";
  return attempt(
    () =>
      staffApi(`/staff/products/${text(form, "product_id")}/stock-adjustments`, {
        method: "POST",
        body: {
          reason: isCount ? "count" : text(form, "reason"),
          ...(isCount ? { new_on_hand: Number(amount) } : { quantity_change: Number(amount) }),
          note: text(form, "note"),
        },
      }),
    "Stock updated.",
  );
}

// Suppliers and purchase orders

export async function saveSupplier(_: FormState, form: FormData): Promise<FormState> {
  const id = text(form, "supplier_id");
  const body = {
    name: text(form, "name"),
    email: optional(form, "email"),
    phone: optional(form, "phone"),
    notes: optional(form, "notes"),
    is_active: id ? form.get("is_active") === "on" : true,
  };
  return attempt(
    () =>
      staffApi<Supplier>(id ? `/staff/suppliers/${id}` : "/staff/suppliers", { method: id ? "PUT" : "POST", body }),
    "Saved.",
  );
}

export async function savePurchaseOrder(_: FormState, form: FormData): Promise<FormState> {
  const id = text(form, "po_id");
  const productIds = form.getAll("product_id").map(String);
  const quantities = form.getAll("quantity").map(String);
  const costs = form.getAll("unit_cost").map(String);
  const items = productIds
    .map((productId, i) => ({ product_id: Number(productId), quantity: Number(quantities[i]), unit_cost: costs[i] }))
    .filter((item) => item.product_id);
  let po: PurchaseOrder;
  try {
    po = await staffApi<PurchaseOrder>(id ? `/staff/purchase-orders/${id}` : "/staff/purchase-orders", {
      method: id ? "PUT" : "POST",
      body: {
        supplier_id: Number(text(form, "supplier_id")),
        expected_at: optional(form, "expected_at"),
        notes: optional(form, "notes"),
        items,
      },
    });
  } catch (error) {
    return failure(error);
  }
  redirect(`/purchase-orders/${po.id}`);
}

export async function purchaseOrderAction(_: FormState, form: FormData): Promise<FormState> {
  const step = text(form, "step");
  if (!["send", "receive", "cancel"].includes(step)) return { error: "Unknown action." };
  return attempt(() => staffApi(`/staff/purchase-orders/${text(form, "po_id")}/${step}`, { method: "POST" }));
}

// Staff

export async function createMember(_: FormState, form: FormData): Promise<FormState> {
  return attempt(
    () =>
      staffApi("/staff/members", {
        method: "POST",
        body: {
          full_name: text(form, "full_name"),
          email: text(form, "email"),
          password: String(form.get("password") ?? ""),
          role: text(form, "role"),
        },
      }),
    "Staff member added.",
  );
}
