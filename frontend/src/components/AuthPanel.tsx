import { useEffect, useRef, useState, type FormEvent } from "react";
import Icon from "./Icon";
import { AuthApiError, authenticate, getCurrentUser } from "../api/auth";
import type { User } from "../types/auth";

export default function AuthPanel({ onUserChange, onRestoringChange }: {
  onUserChange: (user: User | null) => void;
  onRestoringChange: (restoring: boolean) => void;
}) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signupCode, setSignupCode] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const submitting = useRef(false);

  useEffect(() => {
    if (open && !dialogRef.current?.open) dialogRef.current?.showModal();
    else if (!open && dialogRef.current?.open) dialogRef.current.close();
  }, [open]);

  useEffect(() => {
    const show = (event: Event) => {
      if (submitting.current) return;
      setMode((event as CustomEvent).detail === "signup" ? "signup" : "signin");
      setError(""); setPassword(""); setSignupCode(""); setConfirmPassword(""); setOpen(true);
    };
    window.addEventListener("auth:open", show);
    return () => window.removeEventListener("auth:open", show);
  }, []);

  useEffect(() => { onUserChange(user); }, [user, onUserChange]);
  useEffect(() => { onRestoringChange(restoring); }, [restoring, onRestoringChange]);

  useEffect(() => {
    const expired = () => { setUser(null); setError("Your session expired. Please sign in again."); setOpen(true); };
    window.addEventListener("auth:expired", expired);
    return () => window.removeEventListener("auth:expired", expired);
  }, []);

  useEffect(() => {
    let active = true;
    const token = sessionStorage.getItem("access_token");
    if (!token) { setRestoring(false); return; }
    getCurrentUser(token)
      .then(value => { if (active) setUser(value); })
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof AuthApiError && cause.status === 401) sessionStorage.removeItem("access_token");
        setError(cause instanceof Error ? cause.message : "Could not restore your session.");
      })
      .finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!user) return;
    const token = sessionStorage.getItem("access_token");
    if (!token) return;
    // The server is authoritative; this timer also clears expired UI sessions.
    let expiresAt: number;
    try {
      const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
      if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) throw new Error("Invalid expiry");
      expiresAt = payload.exp * 1000;
    } catch {
      sessionStorage.removeItem("access_token"); setUser(null); setError("Invalid session. Please sign in again.");
      return;
    }
    const timer = window.setTimeout(() => {
      sessionStorage.removeItem("access_token");
      setUser(null);
      setError("Your session expired. Please sign in again.");
    }, Math.max(0, expiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [user]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await authenticate(mode, email, password, signupCode);
      sessionStorage.setItem("access_token", result.access_token);
      setUser(result.user);
      setPassword("");
      setSignupCode("");
      setConfirmPassword("");
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not complete authentication.");
    } finally { submitting.current = false; setBusy(false); }
  }

  return (
    <div className="account-control">
      <button className={user ? "account-button" : "primary-button account-signin"} disabled={restoring} onClick={() => { if (!user) setMode("signin"); setOpen(true); }}>
        {user ? <span className="avatar">{user.email[0].toUpperCase()}</span> : <Icon name="user" size={16} />}
        {restoring ? "Loading…" : user ? "My account" : "Sign in"}
      </button>
      <dialog ref={dialogRef} className="auth-dialog" aria-labelledby="auth-heading" onCancel={event => { if (busy) event.preventDefault(); else setOpen(false); }} onClose={() => setOpen(false)}>
      <button className="icon-button dialog-close" disabled={busy} aria-label="Close account dialog" onClick={() => setOpen(false)}><Icon name="close" /></button>
      <div className="dialog-brand"><Icon name="train" size={26} /><span>OptiTrack</span></div>
      <h2 id="auth-heading">{user ? "Your account" : mode === "signup" ? "Create an account" : "Sign in"}</h2>
      <p className="note">{user ? "Your saved plans and schedules are linked to this account." : mode === "signup" ? "Create an account to save your plans." : "Sign in to continue."}</p>
      {restoring ? <p role="status">Checking your session…</p> : user ? (
        <div>
          <p role="status">Signed in as <strong>{user.email}</strong></p>
          <button onClick={() => { sessionStorage.removeItem("access_token"); setUser(null); setError(""); setOpen(false); }}>Sign out</button>
        </div>
      ) : (
        <>
          <div className="auth-tabs" role="group" aria-label="Account action">
            {(["signin", "signup"] as const).map(value => (
              <button key={value} disabled={busy} aria-pressed={mode === value}
                onClick={() => { setMode(value); setError(""); setPassword(""); setSignupCode(""); setConfirmPassword(""); }}>
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
              <label>Confirm password<input type="password" autoComplete="new-password" required minLength={8}
                value={confirmPassword} disabled={busy} onChange={event => setConfirmPassword(event.target.value)} /></label>
              <p className="note">Use at least 8 characters.</p>
              <label>Signup code<input type="password" autoComplete="off" required maxLength={256} value={signupCode}
                disabled={busy} onChange={event => setSignupCode(event.target.value)} /></label>
            </>}
            <button className="primary-button" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}</button>
          </form>
        </>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      </dialog>
    </div>
  );
}
