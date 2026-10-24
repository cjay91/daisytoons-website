const formatter = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** "2800.00" → "Rs 2,800" */
export function rupees(amount: string | number): string {
  return `Rs ${formatter.format(Number(amount))}`;
}
