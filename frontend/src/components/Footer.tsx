import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 text-sm text-muted sm:grid-cols-3">
        <div>
          <p className="font-semibold text-foreground">
            <span className="text-accent">✿</span> Daisytoons
          </p>
          <p className="mt-2">Thoughtful gifts, wrapped with care and delivered across Sri Lanka.</p>
        </div>
        <div className="flex flex-col gap-2">
          <Link href="/shop">Shop all gifts</Link>
          <Link href="/occasions">Shop by occasion</Link>
          <Link href="/account">Your orders</Link>
        </div>
        <div>
          <p>Delivery Rs 400 in Colombo, Rs 650 elsewhere.</p>
          <p className="mt-1">Free delivery on orders over Rs 10,000.</p>
        </div>
      </div>
    </footer>
  );
}
