const formatter = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** "2800.00" → "Rs 2,800" */
export function rupees(amount: string | number): string {
  return `Rs ${formatter.format(Number(amount))}`;
}

const zone = { timeZone: "Asia/Colombo" } as const;

export function dateTime(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleString("en-LK", { ...zone, dateStyle: "medium", timeStyle: "short" });
}

export function shortDate(value: string): string {
  return new Date(value).toLocaleDateString("en-LK", { ...zone, day: "numeric", month: "short" });
}
