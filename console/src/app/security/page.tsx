import type { Metadata } from "next";
import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import { TwoFactorSetup } from "@/components/TwoFactorSetup";
import { requireStaff } from "@/lib/session";

export const metadata: Metadata = { title: "Two-step login" };

export default function SecurityPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Two-step login</h1>
      <Suspense fallback={<Loading />}>
        <Status />
      </Suspense>
    </div>
  );
}

async function Status() {
  const staff = await requireStaff();
  if (staff.two_factor_enabled) {
    return (
      <p className="card p-5 text-sm">
        ✓ Two-step login is on. Each login asks for a code from your authenticator app. If you lose your phone, ask an admin to reset it on the Staff page.
      </p>
    );
  }
  return (
    <section className="card flex flex-col gap-3 p-5">
      <p className="text-sm">
        Staff accounts need a code from your phone as well as your password, so a stolen password alone can&apos;t get into the console.
      </p>
      <TwoFactorSetup />
    </section>
  );
}
