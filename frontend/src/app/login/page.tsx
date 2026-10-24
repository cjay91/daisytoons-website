import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "@/components/AuthForms";

export const metadata: Metadata = { title: "Log in", robots: { index: false } };

export default function LoginPage(props: PageProps<"/login">) {
  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-2xl font-bold">Log in</h1>
      <Suspense fallback={null}>
        <Form searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}

async function Form({ searchParams }: { searchParams: PageProps<"/login">["searchParams"] }) {
  const { next } = await searchParams;
  return <LoginForm next={typeof next === "string" ? next : "/account"} />;
}
