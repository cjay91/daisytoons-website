import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { getCart, getCustomer } from "@/lib/session";

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
        <Link href="/" className="shrink-0 text-xl font-bold tracking-tight">
          <span className="text-accent">✿</span> Daisytoons
        </Link>
        <nav className="hidden gap-5 text-sm font-medium md:flex">
          <Link href="/shop" className="hover:text-brand">
            Shop all
          </Link>
          <Link href="/occasions" className="hover:text-brand">
            Occasions
          </Link>
        </nav>
        <SearchBox id="q-wide" className="ml-auto hidden w-64 sm:block" />
        <div className="ml-auto flex items-center gap-1 sm:ml-2">
          <Suspense fallback={<AccountLinkFallback />}>
            <AccountLink />
          </Suspense>
          <Suspense fallback={<CartLinkView count={0} />}>
            <CartLink />
          </Suspense>
        </div>
      </div>
      <div className="px-4 pb-3 sm:hidden">
        <SearchBox id="q-narrow" />
      </div>
    </header>
  );
}

export function SearchBox({ id, className = "" }: { id: string; className?: string }) {
  return (
    <Form action="/shop" className={className} role="search">
      <label htmlFor={id} className="sr-only">
        Search gifts
      </label>
      <input
        id={id}
        name="q"
        type="search"
        placeholder="Search gifts"
        className="input rounded-full"
      />
    </Form>
  );
}

async function AccountLink() {
  const customer = await getCustomer();
  return (
    <Link href={customer ? "/account" : "/login"} className="btn-outline border-transparent">
      {customer ? customer.full_name.split(" ")[0] : "Log in"}
    </Link>
  );
}

function AccountLinkFallback() {
  return <span className="btn-outline invisible border-transparent">Log in</span>;
}

async function CartLink() {
  const cart = await getCart().catch(() => null);
  return <CartLinkView count={cart?.item_count ?? 0} />;
}

function CartLinkView({ count }: { count: number }) {
  return (
    <Link href="/cart" className="btn-outline" aria-label={`Cart, ${count} items`}>
      Cart
      <span className="min-w-5 rounded-full bg-accent px-1.5 text-center text-xs font-bold text-black">
        {count}
      </span>
    </Link>
  );
}
