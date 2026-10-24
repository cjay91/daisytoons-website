"use client";

import Link from "next/link";
import { useActionState } from "react";

import { login, register, type FormState } from "@/app/actions";

function ErrorText({ text }: { text?: string }) {
  return text ? <p className="mt-1 text-sm text-danger">{text}</p> : null;
}

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(login, {});
  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <input type="hidden" name="next" value={next} />
      <div>
        <label htmlFor="email" className="label">
          Email
        </label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" />
      </div>
      <div>
        <label htmlFor="password" className="label">
          Password
        </label>
        <input id="password" name="password" type="password" autoComplete="current-password" required className="input" />
      </div>
      {state.error && <p role="alert" className="text-sm text-danger">{state.error}</p>}
      <button className="btn py-3" disabled={pending}>
        {pending ? "Logging in…" : "Log in"}
      </button>
      <p className="text-center text-sm text-muted">
        New here?{" "}
        <Link href={`/register?next=${encodeURIComponent(next)}`} className="font-medium text-brand">
          Create an account
        </Link>
      </p>
    </form>
  );
}

export function RegisterForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(register, {});
  const errors = state.fieldErrors ?? {};
  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <input type="hidden" name="next" value={next} />
      <div>
        <label htmlFor="full_name" className="label">
          Full name
        </label>
        <input id="full_name" name="full_name" autoComplete="name" required className="input" />
        <ErrorText text={errors.full_name} />
      </div>
      <div>
        <label htmlFor="email" className="label">
          Email
        </label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" />
        <ErrorText text={errors.email} />
      </div>
      <div>
        <label htmlFor="phone" className="label">
          Mobile number (optional)
        </label>
        <input id="phone" name="phone" type="tel" autoComplete="tel" className="input" />
      </div>
      <div>
        <label htmlFor="password" className="label">
          Password
        </label>
        <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required className="input" />
        <p className="mt-1 text-xs text-muted">At least 8 characters.</p>
        <ErrorText text={errors.password} />
      </div>
      {state.error && !Object.keys(errors).length && <p role="alert" className="text-sm text-danger">{state.error}</p>}
      <button className="btn py-3" disabled={pending}>
        {pending ? "Creating account…" : "Create account"}
      </button>
      <p className="text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href={`/login?next=${encodeURIComponent(next)}`} className="font-medium text-brand">
          Log in
        </Link>
      </p>
    </form>
  );
}
