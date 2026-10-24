import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <p className="text-5xl text-accent">✿</p>
      <h1 className="mt-4 text-2xl font-bold">We couldn&apos;t find that page</h1>
      <p className="mt-2 text-muted">It may have moved, or the gift is no longer sold.</p>
      <Link href="/shop" className="btn mt-6">
        Browse gifts
      </Link>
    </div>
  );
}
