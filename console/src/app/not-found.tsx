import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card mx-auto mt-12 max-w-md p-8 text-center">
      <h1 className="text-xl font-semibold">Not found</h1>
      <p className="mt-2 text-muted">That order, product or page doesn&apos;t exist.</p>
      <Link href="/" className="btn mt-4">
        Back to the dashboard
      </Link>
    </div>
  );
}
