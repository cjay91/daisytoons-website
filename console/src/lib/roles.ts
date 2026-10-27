import type { StaffRole } from "./types";

// What each role can open. The API checks every request; this only decides what the menu shows.
// Keep in step with backend/app/permissions.py.
export type Area = "orders" | "products" | "stock" | "purchasing" | "reports" | "staff";

const AREAS: Record<StaffRole, Area[]> = {
  admin: ["orders", "products", "stock", "purchasing", "reports", "staff"],
  packer: ["orders", "products", "stock"],
  support: ["orders", "products"],
};

export function can(role: StaffRole, area: Area): boolean {
  return AREAS[role].includes(area);
}
