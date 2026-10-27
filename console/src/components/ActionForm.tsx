"use client";

import { useActionState, type ReactNode } from "react";

import type { FormState } from "@/app/actions";

type Props = {
  action: (state: FormState, form: FormData) => Promise<FormState>;
  submit: string;
  pending?: string;
  // Sent with the form, such as the order number.
  hidden?: Record<string, string | number>;
  variant?: "primary" | "outline" | "danger";
  // Asked before submitting, for steps that are hard to undo.
  confirm?: string;
  className?: string;
  children?: ReactNode;
};

/** A form that runs a Server Action and shows its error or success message. */
export function ActionForm({ action, submit, pending, hidden = {}, variant = "primary", confirm, className, children }: Props) {
  const [state, run, busy] = useActionState<FormState, FormData>(action, {});
  const button = { primary: "btn", outline: "btn-outline", danger: "btn-danger" }[variant];
  return (
    <form
      action={run}
      className={className ?? "flex flex-col gap-3"}
      onSubmit={(event) => {
        if (confirm && !window.confirm(confirm)) event.preventDefault();
      }}
    >
      {Object.entries(hidden).map(([name, value]) => (
        <input key={name} type="hidden" name={name} value={value} />
      ))}
      {children}
      <div className="flex flex-wrap items-center gap-3">
        <button className={button} disabled={busy}>
          {busy ? (pending ?? "Saving…") : submit}
        </button>
        {state.error && (
          <p role="alert" className="text-sm text-danger">
            {state.error}
          </p>
        )}
        {state.ok && state.message && (
          <p role="status" className="text-sm text-ok">
            {state.message}
          </p>
        )}
      </div>
    </form>
  );
}
