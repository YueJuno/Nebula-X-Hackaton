import { useEffect, useState, type FormEvent } from "react";
import { authenticate, getCurrentUser } from "../api/auth";
import type { User } from "../types/auth";

export default function AuthPanel() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signupCode, setSignupCode] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const token = sessionStorage.getItem("access_token");
    if (!token) { setRestoring(false); return; }
    getCurrentUser(token)
      .then(value => { if (active) setUser(value); })
      .catch(() => { if (active) sessionStorage.removeItem("access_token"); })
      .finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!user) return;
    const token = sessionStorage.getItem("access_token");
    if (!token) return;
    // The server is authoritative; this timer also clears expired UI sessions.
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    const timer = window.setTimeout(() => {
      sessionStorage.removeItem("access_token");
      setUser(null);
      setError("Your session expired. Please sign in again.");
    }, Math.max(0, payload.exp * 1000 - Date.now()));
    return () => window.clearTimeout(timer);
  }, [user]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await authenticate(mode, email, password, signupCode);
      sessionStorage.setItem("access_token", result.access_token);
      setUser(result.user);
      setPassword("");
      setSignupCode("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not complete authentication.");
    } finally { setBusy(false); }
  }

  return (
    <section className="panel" aria-labelledby="auth-heading">
      <h2 id="auth-heading">{user ? "Your account" : mode === "signup" ? "Create an account" : "Sign in"}</h2>
      {restoring ? <p role="status">Checking your session…</p> : user ? (
        <div>
          <p role="status">Signed in as <strong>{user.email}</strong></p>
          <button onClick={() => { sessionStorage.removeItem("access_token"); setUser(null); setError(""); }}>Sign out</button>
        </div>
      ) : (
        <>
          <div className="auth-tabs" role="group" aria-label="Account action">
            {(["signin", "signup"] as const).map(value => (
              <button key={value} disabled={busy} aria-pressed={mode === value}
                onClick={() => { setMode(value); setError(""); setPassword(""); setSignupCode(""); }}>
                {value === "signin" ? "Sign in" : "Sign up"}
              </button>
            ))}
          </div>
          <form className="auth-form" onSubmit={submit}>
            <label>Email<input type="email" autoComplete="email" required maxLength={254} value={email} disabled={busy}
              onChange={event => setEmail(event.target.value)} /></label>
            <label>Password<input type="password" autoComplete={mode === "signup" ? "new-password" : "current-password"}
              required minLength={8} value={password} disabled={busy} onChange={event => setPassword(event.target.value)} /></label>
            {mode === "signup" && <>
              <p className="note">Use at least 8 characters. Passwords may contain at most 72 UTF-8 bytes.</p>
              <label>Signup code<input type="password" autoComplete="off" required maxLength={256} value={signupCode}
                disabled={busy} onChange={event => setSignupCode(event.target.value)} /></label>
            </>}
            <button type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}</button>
          </form>
        </>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
