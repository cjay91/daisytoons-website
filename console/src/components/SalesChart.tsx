import { rupees, shortDate } from "@/lib/format";
import type { DailyReport } from "@/lib/types";

/** Revenue for each of the last 14 days, as bars. One series, so the heading names it. */
export function SalesChart({ days, selected }: { days: DailyReport["last_14_days"]; selected: string }) {
  const max = Math.max(...days.map((d) => Number(d.revenue)), 1);
  return (
    <figure>
      <div className="flex h-40 items-end gap-0.5 border-b border-line" role="img" aria-label="Revenue for the last 14 days">
        {days.map((d) => (
          <a
            key={d.day}
            href={`/reports?day=${d.day}`}
            className="group relative flex h-full flex-1 items-end justify-center"
            aria-label={`${shortDate(d.day)}: ${rupees(d.revenue)} from ${d.orders} orders`}
          >
            <span
              className={`w-full max-w-8 rounded-t ${d.day === selected ? "bg-brand" : "bg-accent group-hover:bg-brand"}`}
              style={{ height: `${(Number(d.revenue) / max) * 100}%`, minHeight: Number(d.revenue) ? 2 : 0 }}
            />
            <span className="pointer-events-none absolute bottom-full z-10 mb-1 hidden whitespace-nowrap rounded-md border border-line bg-surface px-2 py-1 text-xs shadow group-hover:block group-focus:block">
              <strong>{shortDate(d.day)}</strong>
              <br />
              {rupees(d.revenue)} · {d.orders} {d.orders === 1 ? "order" : "orders"}
            </span>
          </a>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>{shortDate(days[0].day)}</span>
        <span>{shortDate(days[days.length - 1].day)}</span>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Show as a table</summary>
        <table className="table mt-2">
          <thead>
            <tr>
              <th>Day</th>
              <th className="text-right">Orders</th>
              <th className="text-right">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.day}>
                <td>{shortDate(d.day)}</td>
                <td className="text-right tabular-nums">{d.orders}</td>
                <td className="text-right tabular-nums">{rupees(d.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
