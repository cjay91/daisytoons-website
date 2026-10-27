import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { SalesChart } from "@/components/SalesChart";
import { query } from "@/lib/api";
import { rupees } from "@/lib/format";
import { staffApi } from "@/lib/session";
import type { DailyReport } from "@/lib/types";

export const metadata: Metadata = { title: "Sales" };

export default function ReportsPage({ searchParams }: PageProps<"/reports">) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Daily sales</h1>
      <Suspense fallback={<Loading />}>
        <Report searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Report({ searchParams }: Pick<PageProps<"/reports">, "searchParams">) {
  const { day } = await searchParams;
  const report = await staffApi<DailyReport>(`/staff/reports/daily${query({ day: typeof day === "string" ? day : undefined })}`);
  const tiles: [string, string | number][] = [
    ["Revenue", rupees(report.revenue)],
    ["Paid orders", report.orders],
    ["Items sold", report.items_sold],
    ["Average order", rupees(report.average_order)],
    ["Refunds", rupees(report.refunds)],
  ];
  const label = new Date(`${report.day}T00:00:00`).toLocaleDateString("en-LK", { dateStyle: "full" });

  return (
    <>
      <Form action="/reports" className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor="day" className="label">
            Day (Sri Lanka time)
          </label>
          <input id="day" name="day" type="date" defaultValue={report.day} className="input" />
        </div>
        <button className="btn-outline">Show</button>
        <span className="ml-2 self-center text-sm text-muted">{label}</span>
      </Form>

      <section className="grid gap-3 sm:grid-cols-5">
        {tiles.map(([name, value]) => (
          <div key={name} className="card p-4">
            <p className="text-sm text-muted">{name}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <h2 className="mb-3 font-semibold">Revenue, last 14 days</h2>
          <SalesChart days={report.last_14_days} selected={report.day} />
        </section>
        <section className="card flex flex-col gap-2 p-4 text-sm">
          <h2 className="font-semibold">Right now</h2>
          <Link href="/orders" className="flex justify-between hover:underline">
            <span>Waiting to ship</span>
            <strong className="tabular-nums">{report.waiting_to_ship}</strong>
          </Link>
          <Link href="/orders?view=attention" className="flex justify-between hover:underline">
            <span>Need attention</span>
            <strong className="tabular-nums">{report.needs_attention}</strong>
          </Link>
          <Link href="/stock" className="flex justify-between hover:underline">
            <span>Products to reorder</span>
            <strong className="tabular-nums">{report.low_stock}</strong>
          </Link>
        </section>
      </div>

      <section className="card p-4">
        <h2 className="mb-2 font-semibold">Best sellers that day</h2>
        {report.top_products.length === 0 ? (
          <p className="text-sm text-muted">No sales that day.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="text-right">Sold</th>
                <th className="text-right">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {report.top_products.map((p) => (
                <tr key={p.product_id}>
                  <td>
                    <Link href={`/products/${p.product_id}`} className="hover:underline">
                      {p.name}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums">{p.quantity}</td>
                  <td className="text-right tabular-nums">{rupees(p.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
