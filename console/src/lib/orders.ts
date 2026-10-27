import "server-only";

import { notFound } from "next/navigation";

import { ApiError } from "./api";
import { staffApi } from "./session";
import type { Order } from "./types";

export async function loadOrder(number: string): Promise<Order> {
  try {
    return await staffApi<Order>(`/staff/orders/${encodeURIComponent(number)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}
