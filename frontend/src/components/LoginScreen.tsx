import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { api } from "../lib/api";
import type { AuthUser } from "../lib/types";
import { Button, Card } from "./ui";

const passwordRules = [
  {
    label: "12–128 characters",
    test: (value: string) => value.length >= 12 && value.length <= 128,
  },
  {
    label: "One uppercase letter",
    test: (value: string) => [...value].some((character) => character.toUpperCase() === character && character.toLowerCase() !== character),
  },
  {
    label: "One lowercase letter",
    test: (value: string) => [...value].some((character) => character.toLowerCase() === character && character.toUpperCase() !== character),
  },
  {
    label: "One number",
    test: (value: string) => [...value].some((character) => /\d/.test(character)),
  },
  {
    label: "One symbol",
    test: (value: string) => [...value].some((character) => !character.match(/[\p{L}\p{N}\s]/u)),
  },
  {
    label: "No spaces",
    test: (value: string) => !/\s/.test(value),
  },
] as const;

export function LoginScreen({
  onAuthenticated,
  initialError = "",
}: {
  onAuthenticated: (user: AuthUser) => void;
  initialError?: string;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(initialError);
  const [loading, setLoading] = useState(false);
  const passwordRuleResults = passwordRules.map((rule) => ({
    ...rule,
    passed: rule.test(password),
  }));
  const passwordMeetsPolicy = passwordRuleResults.every((rule) => rule.passed);

  useEffect(() => {
    setError(initialError);
  }, [initialError]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username || !password || loading) return;
    setLoading(true);
    setError("");
    try {
      onAuthenticated(await api.login(username, password));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-[#07110f] px-5 py-10 text-[#edf4f1]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_75%_10%,rgba(185,245,91,.14),transparent_34%),radial-gradient(circle_at_10%_80%,rgba(73,220,177,.09),transparent_30%)]" />
      <div className="relative grid w-full max-w-5xl gap-8 lg:grid-cols-[1.1fr_.9fr] lg:items-center">
        <section>
          <div className="mb-8 flex items-center gap-4">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#b9f55b] text-[#07110f] shadow-[0_0_30px_rgba(185,245,91,.18)]">
              <Activity size={24} strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight">
                Logistics Intelligence
              </p>
              <p className="text-xs text-[#8ba39c]">
                Secure operational analytics
              </p>
            </div>
          </div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[.2em] text-[#b9f55b]">
            Reviewer access
          </p>
          <h1 className="max-w-xl text-4xl font-semibold tracking-[-.045em] sm:text-5xl">
            Your logistics data,
            <br />
            <span className="text-[#8ba39c]">behind one secure session.</span>
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-[#93a49e]">
            Sign in to explore operational metrics, ask grounded analytical
            questions, and continue saved forecasting conversations.
          </p>
          <div className="mt-8 flex flex-wrap gap-4 text-xs text-[#9dafaa]">
            <span className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#49dcb1]" />
              HttpOnly session
            </span>
            <span className="flex items-center gap-2">
              <LockKeyhole size={14} className="text-[#49dcb1]" />
              Account-owned history
            </span>
          </div>
        </section>

        <Card className="border-white/10 bg-[#0d1917]/95 p-6 shadow-2xl sm:p-8">
          <div className="mb-6">
            <p className="text-xl font-semibold">Sign in</p>
            <p className="mt-2 text-sm leading-6 text-[#93a49e]">
              Use the reviewer credentials supplied with the submission.
            </p>
          </div>
          <form className="grid gap-4" onSubmit={submit}>
            <label className="grid gap-2 text-xs font-medium text-[#b9c7c2]">
              Username
              <input
                autoFocus
                required
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="h-12 rounded-xl border border-white/10 bg-[#07110f] px-4 text-sm text-white outline-none transition placeholder:text-[#60736d] focus:border-[#b9f55b]/50 focus:ring-2 focus:ring-[#b9f55b]/10"
                placeholder="Enter username"
              />
            </label>
            <div className="grid gap-2 text-xs font-medium text-[#b9c7c2]">
              <label htmlFor="login-password">Password</label>
              <span className="relative block">
                <input
                  id="login-password"
                  required
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  aria-describedby="password-requirements"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-12 w-full rounded-xl border border-white/10 bg-[#07110f] px-4 pr-12 text-sm text-white outline-none transition placeholder:text-[#60736d] focus:border-[#b9f55b]/50 focus:ring-2 focus:ring-[#b9f55b]/10"
                  placeholder="Enter password"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute inset-y-0 right-0 grid w-12 place-items-center rounded-r-xl text-[#71837d] transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#b9f55b]"
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
            </div>
            <div
              id="password-requirements"
              aria-live="polite"
              className="rounded-xl border border-white/8 bg-black/10 p-3"
            >
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[.14em] text-[#8fa19b]">
                Must contain
              </p>
              <ul className="grid grid-cols-2 gap-x-3 gap-y-2">
                {passwordRuleResults.map((rule) => (
                  <li
                    key={rule.label}
                    className={`flex items-center gap-1.5 text-[11px] transition ${
                      rule.passed ? "text-[#72ebc8]" : "text-[#71837d]"
                    }`}
                  >
                    <span
                      className={`grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full border ${
                        rule.passed
                          ? "border-[#49dcb1]/50 bg-[#49dcb1]/10"
                          : "border-white/15"
                      }`}
                      aria-hidden="true"
                    >
                      {rule.passed && <Check size={9} strokeWidth={3} />}
                    </span>
                    {rule.label}
                  </li>
                ))}
              </ul>
            </div>
            {error && (
              <p
                role="alert"
                className="rounded-xl border border-[#df6f74]/25 bg-[#df6f74]/8 p-3 text-xs leading-5 text-[#f5b1b4]"
              >
                {error}
              </p>
            )}
            <Button
              type="submit"
              className="mt-2 h-12 w-full"
              disabled={loading || !username || !passwordMeetsPolicy}
            >
              {loading ? "Signing in…" : "Continue"}
              {!loading && <ArrowRight size={16} />}
            </Button>
          </form>
          <p className="mt-5 text-center text-[11px] leading-5 text-[#71837d]">
            Sessions expire automatically. Credentials are verified only by the
            backend and are never stored in the browser.
          </p>
        </Card>
      </div>
    </main>
  );
}
