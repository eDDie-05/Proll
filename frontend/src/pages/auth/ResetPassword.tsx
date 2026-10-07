import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { Alert, Spinner } from "../../components/ui";
import { AuthShell } from "./AuthShell";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/password-reset/confirm/", { uid, token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  if (!uid || !token) {
    return (
      <AuthShell title="Invalid link">
        <Alert>This reset link is incomplete. Request a new one.</Alert>
        <Link to="/forgot-password" className="btn-secondary mt-4 w-full">Request new link</Link>
      </AuthShell>
    );
  }
  return (
    <AuthShell title="Choose a new password">
      {done ? (
        <div className="space-y-4">
          <Alert kind="success">Your password has been changed.</Alert>
          <Link to="/login" className="btn-primary w-full">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <div>
            <label className="label" htmlFor="pw">New password</label>
            <input id="pw" type="password" autoComplete="new-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="mt-1 text-xs text-slate-500">At least 10 characters; avoid common or purely numeric passwords.</p>
          </div>
          <div>
            <label className="label" htmlFor="pw2">Confirm password</label>
            <input id="pw2" type="password" autoComplete="new-password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <button className="btn-primary w-full" disabled={busy || !password}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Reset password
          </button>
        </form>
      )}
    </AuthShell>
  );
}
