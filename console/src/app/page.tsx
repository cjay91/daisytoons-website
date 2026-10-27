import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { rupees } from "@/lib/format";
import { can } from "@/lib/roles";
import { requireStaff, staffApi } from "@/lib/session";
import type { DailyReport, OrderList } from "@/lib/types";

export default function Home() {
  return (
    <Suspense fallback={<Loading />}>
      <Dashboard />
    </Suspense>
  );
}

async function count(path: string): Promise<number> {
  return (await staffApi<OrderList>(path)).total;
}

async function Dashboard() {
  const staff = await requireStaff();
  const [toPack, packing, attention, report] = await Promise.all([
    count("/staff/orders?status=paid&limit=1"),
    count("/staff/orders?status=packing&limit=1"),
    count("/staff/orders?needs_attention=true&limit=1"),
    can(staff.role, "reports") ? staffApi<DailyReport>("/staff/reports/daily") : null,
  ]);
  const tiles = [
    { label: "Paid, waiting to pack", value: toPack, href: "/orders?status=paid" },
    { label: "Being packed", value: packing, href: "/packing" },
    { label: "Need attention", value: attention, href: "/orders?view=attention" },
  ];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Hello, {staff.full_name.split(" ")[0]}</h1>
      <div className="grid gap-4 sm:grid-cols-3">
        {tiles.map((tile) => (
          <Link key={tile.label} href={tile.href} className="card p-5 hover:border-foreground">
            <p className="text-sm text-muted">{tile.label}</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums">{tile.value}</p>
          </Link>
        ))}
      </div>
      {report && (
        <Link href="/reports" className="card grid gap-4 p-5 hover:border-foreground sm:grid-cols-4">
          <div>
            <p className="text-sm text-muted">Sales today</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{rupees(report.revenue)}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Orders today</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{report.orders}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Items sold</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{report.items_sold}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Products to reorder</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{report.low_stock}</p>
          </div>
        </Link>
      )}
    </div>
  );
}
