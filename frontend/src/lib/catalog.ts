import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import { api, ApiError, query } from "./api";
import type { Product, Tag } from "./types";

// Catalog reads are cached for a few minutes, so busy pages don't hit the API on every
// visit. Stock shown here can be a little behind; the cart and checkout always check live.

export type ProductFilters = {
  q?: string;
  occasion?: string;
  recipient?: string;
  min_price?: string;
  max_price?: string;
  sort?: string;
};

export async function getProducts(filters: ProductFilters = {}): Promise<Product[]> {
  "use cache";
  cacheLife("minutes");
  cacheTag("products");
  return api<Product[]>(`/products${query(filters)}`);
}

export async function getProduct(slug: string): Promise<Product | null> {
  "use cache";
  cacheLife("minutes");
  cacheTag("products");
  try {
    return await api<Product>(`/products/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getTags(): Promise<Tag[]> {
  "use cache";
  cacheLife("hours");
  cacheTag("tags");
  return api<Tag[]>("/tags");
}

export async function getDistricts(): Promise<string[]> {
  "use cache";
  cacheLife("days");
  return api<string[]>("/checkout/districts");
}
