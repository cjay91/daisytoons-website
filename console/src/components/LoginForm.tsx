"use client";

import { useActionState } from "react";

import { login, loginCode, type FormState } from "@/app/actions";

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(login, {});
  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <input type="hidden" name="next" value={next} />
      <div>
        <label htmlFor="email" className="label">
          Email
        </label>
        <input id="email" name="email" type="email" autoComplete="username" required className="input" />
      </div>
      <div>
        <label htmlFor="password" className="label">
          Password
        </label>
        <input id="password" name="password" type="password" autoComplete="current-password" required className="input" />
      </div>
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
      <button className="btn py-2.5" disabled={pending}>
        {pending ? "Logging in…" : "Log in"}
      </button>
    </form>
  );
}

export function CodeForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(loginCode, {});
  return (
    <form action={action} className="card flex flex-col gap-4 p-6">
      <input type="hidden" name="next" value={next} />
      <div>
        <label htmlFor="code" className="label">
          Code
        </label>
        <input
          id="code"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9 ]{6,8}"
          required
          autoFocus
          className="input text-center font-mono text-xl tracking-widest"
        />
      </div>
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
      <button className="btn py-2.5" disabled={pending}>
        {pending ? "Checking…" : "Log in"}
      </button>
      <a href="/login" className="text-center text-sm text-muted">
        Start again
      </a>
    </form>
  );
}
