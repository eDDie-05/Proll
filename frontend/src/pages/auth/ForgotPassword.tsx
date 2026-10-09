import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { Alert, Spinner } from "../../components/ui";
import { AuthShell } from "./AuthShell";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.post("/auth/password-reset/", { email });
      setDone(r.data.detail);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthShell title="Reset your password">
      {done ? (
        <div className="space-y-4">
          <Alert kind="success">{done}</Alert>
          <Link to="/login" className="btn-secondary w-full">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <p className="text-sm text-slate-600">Enter the email address on your account and we will send you a reset link.</p>
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <button className="btn-primary w-full" disabled={busy || !email}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Send reset link
          </button>
          <p className="text-center text-sm"><Link to="/login" className="text-brand-600 hover:underline">Back to sign in</Link></p>
        </form>
      )}
    </AuthShell>
  );
}
