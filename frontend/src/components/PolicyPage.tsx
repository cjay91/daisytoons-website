import Link from "next/link";
import type { ReactNode } from "react";

import { POLICIES, SHOP } from "@/lib/shop";

export function PolicyPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-[12rem_1fr]">
      <nav aria-label="Policies" className="flex flex-wrap gap-x-4 gap-y-2 text-sm md:flex-col">
        {POLICIES.map((policy) => (
          <Link key={policy.href} href={policy.href} className="text-muted hover:text-foreground">
            {policy.label}
          </Link>
        ))}
      </nav>
      <article className="flex flex-col gap-4 leading-relaxed [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc">
        <h1 className="text-3xl font-semibold">{title}</h1>
        {children}
        <p className="mt-6 text-sm text-muted">
          Last updated {SHOP.policiesUpdated}. Questions? Email{" "}
          <a href={`mailto:${SHOP.email}`} className="text-brand">
            {SHOP.email}
          </a>
          .
        </p>
      </article>
    </div>
  );
}
