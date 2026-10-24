import Link from "next/link";

import { logout } from "@/app/actions";

export default function AccountLayout({ children }: LayoutProps<"/account">) {
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-2 border-b border-line pb-4">
        <h1 className="mr-auto text-2xl font-bold">Your account</h1>
        <Link href="/account" className="btn-outline">
          Orders
        </Link>
        <Link href="/account/addresses" className="btn-outline">
          Addresses
        </Link>
        <form action={logout}>
          <button className="btn-outline">Log out</button>
        </form>
      </div>
      {children}
    </div>
  );
}
