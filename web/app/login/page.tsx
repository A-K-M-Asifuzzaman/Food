"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "../components/AuthProvider";

/** Firebase surfaces machine codes. */
function explain(code: string, fallback: string): string {
  const map: Record<string, string> = {
    "auth/invalid-credential": "That email and password do not match an account.",
    "auth/invalid-email": "That does not look like an email address.",
    "auth/user-not-found": "No account with that email. Create one below.",
    "auth/wrong-password": "That password is not right.",
    "auth/email-already-in-use": "That email already has an account — sign in instead.",
    "auth/weak-password": "Passwords need at least six characters.",
    "auth/popup-closed-by-user": "The Google window closed before sign-in finished.",
    "auth/popup-blocked": "Your browser blocked the Google window. Allow pop-ups and retry.",
    "auth/network-request-failed": "Could not reach Firebase. Check your connection.",
    "auth/too-many-requests": "Too many attempts. Wait a minute and try again.",
    "auth/operation-not-allowed":
      "That sign-in method is not enabled on the Firebase project yet.",
  };
  return map[code] ?? fallback;
}

function LoginForm() {
  const { user, loading, signInWithGoogle, signInWithPassword, registerWithPassword } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/analyze";

  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already signed in — nobody wants to look at a login form they do not need.
  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, next, router]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      router.replace(next);
    } catch (err: unknown) {
      const e = err as { code?: string; message?: string };
      setError(explain(e.code ?? "", e.message ?? "Sign-in failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex-1 w-full">
      <section className="mx-auto max-w-md px-5 py-10 sm:py-16">
        <p className="text-xs uppercase tracking-[0.28em] text-[var(--text-dim)]">
          Issue 01 · Access
        </p>
        <h1 className="font-display text-4xl sm:text-5xl leading-none mt-3">
          {mode === "in" ? "WELCOME BACK" : "GET YOUR MASK"}
        </h1>
        <p className="mt-3 text-[var(--text-dim)]">
          {mode === "in"
            ? "Sign in to analyse a photo and keep a record of everything you have."
            : "An account keeps your predictions, your questions and your corrections together in one place."}
        </p>

        <div className="panel p-5 sm:p-6 mt-6">
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(signInWithGoogle)}
            className="w-full ink-edge px-4 py-3 font-display uppercase tracking-wide flex items-center justify-center gap-3 disabled:opacity-50"
          >
            {/* Google's mark, inlined — an external image would be blocked and
                a text "G" reads as a placeholder. */}
            <svg viewBox="0 0 48 48" className="w-5 h-5 shrink-0" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z" />
              <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
              <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
              <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.6l6.2 5.2C37 41 44 36 44 24c0-1.3-.1-2.6-.4-3.9z" />
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 my-5" aria-hidden="true">
            <span className="flex-1 h-px bg-[var(--line)] opacity-30" />
            <span className="text-xs uppercase tracking-widest text-[var(--text-dim)]">or</span>
            <span className="flex-1 h-px bg-[var(--line)] opacity-30" />
          </div>

          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void run(() =>
                mode === "in"
                  ? signInWithPassword(email, password)
                  : registerWithPassword(name, email, password),
              );
            }}
          >
            {mode === "up" && (
              <Field
                label="Name"
                value={name}
                onChange={setName}
                type="text"
                autoComplete="name"
                placeholder="Peter Parker"
              />
            )}
            <Field
              label="Email"
              value={email}
              onChange={setEmail}
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
            />
            <Field
              label="Password"
              value={password}
              onChange={setPassword}
              type="password"
              autoComplete={mode === "in" ? "current-password" : "new-password"}
              placeholder="At least six characters"
              required
            />

            {error && (
              <p
                className="text-sm ink-edge px-3 py-2"
                role="alert"
                style={{ background: "var(--color-amber)", color: "#0b0b0f" }}
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full ink-edge px-4 py-3 font-display uppercase tracking-wide disabled:opacity-50"
              style={{ background: "var(--color-red)", color: "#f4f1e8" }}
            >
              {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="mt-4 text-sm text-[var(--text-dim)]">
            {mode === "in" ? "No account yet?" : "Already have one?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "in" ? "up" : "in");
                setError(null);
              }}
              className="underline"
              style={{ color: "var(--color-blue)" }}
            >
              {mode === "in" ? "Create one" : "Sign in"}
            </button>
          </p>
        </div>

        <p className="mt-5 text-xs text-[var(--text-dim)]">
          Your photograph is analysed and never stored — only the dish name, the confidence and
          the timestamp are kept, so you can see your own history. You can{" "}
          <Link href="/history" className="underline">
            review or delete
          </Link>{" "}
          that record at any time.
        </p>
      </section>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  ...rest
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</span>
      <input
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full ink-edge px-3 py-2.5 bg-transparent"
      />
    </label>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="flex-1" />}>
      <LoginForm />
    </Suspense>
  );
}
