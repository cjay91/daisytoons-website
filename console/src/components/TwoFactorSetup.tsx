"use client";

import { useActionState } from "react";

import { enableTwoFactor, startTwoFactor, type FormState, type SetupState } from "@/app/actions";

export function TwoFactorSetup() {
  const [setup, start, starting] = useActionState<SetupState>(startTwoFactor, {});
  const [state, enable, enabling] = useActionState<FormState, FormData>(enableTwoFactor, {});

  if (!setup.secret) {
    return (
      <form action={start} className="flex flex-col gap-3">
        <p className="text-sm">
          You&apos;ll need an authenticator app on your phone, such as Google Authenticator, Microsoft Authenticator or 1Password.
        </p>
        {setup.error && (
          <p role="alert" className="text-sm text-danger">
            {setup.error}
          </p>
        )}
        <button className="btn self-start" disabled={starting}>
          {starting ? "Starting…" : "Set up two-step login"}
        </button>
      </form>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm">
        <li>In your authenticator app, add an account and scan this code.</li>
        <li>Type the 6-digit code the app shows.</li>
      </ol>
      {/* The SVG is made on our own server from the setup link; it holds no scripts. */}
      <div className="w-52 rounded-lg bg-white p-2" dangerouslySetInnerHTML={{ __html: setup.qr ?? "" }} />
      <p className="text-sm text-muted">
        Can&apos;t scan? Enter this key instead: <span className="font-mono text-foreground">{setup.secret.match(/.{1,4}/g)?.join(" ")}</span>
      </p>
      <form action={enable} className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="setup-code" className="label">
            Code from the app
          </label>
          <input id="setup-code" name="code" inputMode="numeric" autoComplete="one-time-code" required className="input w-40 font-mono" />
        </div>
        <button className="btn" disabled={enabling}>
          {enabling ? "Checking…" : "Turn on"}
        </button>
        {state.error && (
          <p role="alert" className="w-full text-sm text-danger">
            {state.error}
          </p>
        )}
      </form>
    </div>
  );
}
