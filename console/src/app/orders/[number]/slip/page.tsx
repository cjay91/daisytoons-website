import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { PackingSlip } from "@/components/PackingSlip";
import { PrintButton } from "@/components/PrintButton";
import { loadOrder } from "@/lib/orders";

export const metadata: Metadata = { title: "Packing slip" };

export default function SlipPage({ params }: PageProps<"/orders/[number]/slip">) {
  return (
    <Suspense fallback={<Loading />}>
      <Slip params={params} />
    </Suspense>
  );
}

async function Slip({ params }: Pick<PageProps<"/orders/[number]/slip">, "params">) {
  const { number } = await params;
  const order = await loadOrder(number);
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center gap-3 print:hidden">
        <Link href={`/orders/${order.order_number}`} className="text-sm text-muted">
          ← {order.order_number}
        </Link>
        <span className="ml-auto" />
        <PrintButton label="Print slip and label" />
      </div>
      <div className="card overflow-hidden">
        <PackingSlip order={order} />
      </div>
    </div>
  );
}
