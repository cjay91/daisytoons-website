import type { Metadata } from "next";
import { Suspense } from "react";

import { RegisterForm } from "@/components/AuthForms";

export const metadata: Metadata = { title: "Create an account", robots: { index: false } };

export default function RegisterPage(props: PageProps<"/register">) {
  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-2xl font-bold">Create an account</h1>
      <Suspense fallback={null}>
        <Form searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}

async function Form({ searchParams }: { searchParams: PageProps<"/register">["searchParams"] }) {
  const { next } = await searchParams;
  return <RegisterForm next={typeof next === "string" ? next : "/account"} />;
}
