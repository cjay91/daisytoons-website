export function Loading({ text = "Loading…" }: { text?: string }) {
  return <p className="text-muted">{text}</p>;
}
