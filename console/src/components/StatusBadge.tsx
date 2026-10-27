import type { OrderStatus, PurchaseOrderStatus } from "@/lib/types";

const STYLES: Record<string, string> = {
  pending: "bg-line text-muted",
  paid: "bg-accent-soft text-foreground",
  packing: "bg-info-soft text-info",
  shipped: "bg-info-soft text-info",
  delivered: "bg-ok-soft text-ok",
  cancelled: "bg-line text-muted",
  refunded: "bg-danger-soft text-danger",
  draft: "bg-line text-muted",
  sent: "bg-info-soft text-info",
  received: "bg-ok-soft text-ok",
};

export function StatusBadge({ status }: { status: OrderStatus | PurchaseOrderStatus }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${STYLES[status]}`}>
      {status}
    </span>
  );
}
