import type { Metadata } from "next";
import { Suspense } from "react";

import { CodeForm } from "@/components/LoginForm";

export const metadata: Metadata = { title: "Login code" };

export default function CodePage({ searchParams }: PageProps<"/login/code">) {
  return (
    <div className="mx-auto mt-16 w-full max-w-sm">
      <h1 className="mb-2 text-center text-2xl font-semibold">Enter your code</h1>
      <p className="mb-6 text-center text-sm text-muted">Open your authenticator app and type the 6-digit code for Daisytoons console.</p>
      <Suspense fallback={<div className="card h-40" />}>
        <Form searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Form({ searchParams }: Pick<PageProps<"/login/code">, "searchParams">) {
  const { next } = await searchParams;
  return <CodeForm next={typeof next === "string" ? next : "/"} />;
}
