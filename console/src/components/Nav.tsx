import Link from "next/link";

import { logout } from "@/app/actions";
import { can, type Area } from "@/lib/roles";
import { getStaff } from "@/lib/session";

const LINKS: { href: string; label: string; area: Area }[] = [
  { href: "/orders", label: "Orders", area: "orders" },
  { href: "/packing", label: "Packing", area: "orders" },
  { href: "/products", label: "Products", area: "products" },
  { href: "/stock", label: "Low stock", area: "stock" },
  { href: "/suppliers", label: "Suppliers", area: "purchasing" },
  { href: "/purchase-orders", label: "Purchase orders", area: "purchasing" },
  { href: "/reports", label: "Sales", area: "reports" },
  { href: "/staff", label: "Staff", area: "staff" },
];

export async function Nav() {
  const staff = await getStaff();
  if (!staff) return null;
  return (
    <header className="border-b border-line bg-surface print:hidden">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <Link href="/" className="font-semibold">
          Daisytoons <span className="text-muted">console</span>
        </Link>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {LINKS.filter((link) => can(staff.role, link.area)).map((link) => (
            <Link key={link.href} href={link.href} className="text-muted hover:text-foreground">
              {link.label}
            </Link>
          ))}
        </nav>
        <form action={logout} className="ml-auto flex items-center gap-3 text-sm">
          <Link href="/security" className="text-muted hover:text-foreground">
            {staff.full_name} · <span className="capitalize">{staff.role}</span>
            {!staff.two_factor_enabled && <span className="ml-1 text-danger">· set up two-step login</span>}
          </Link>
          <button className="btn-outline py-1">Log out</button>
        </form>
      </div>
    </header>
  );
}
