import React, { useState, useEffect } from "react";
import { AuthAPI } from "../api/endpoints";
import { ThemeToggle } from "../contexts/ThemeContext";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [changeSession, setChangeSession] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState("checking");

  const checkApi = async () => {
    setApiStatus("checking");
    try {
      await AuthAPI.health();
      setApiStatus("ready");
    } catch {
      setApiStatus("offline");
    }
  };

  useEffect(() => {
    checkApi();
    const checkAuth = async () => {
      const existingToken = localStorage.getItem("lexecon_token");
      if (existingToken) {
        try {
          const res = await AuthAPI.me();
          setStatus(`✅ Already authenticated as: ${res?.data?.user?.email || "user"}`);
        } catch (e) {
          localStorage.removeItem("lexecon_token");
        }
      }
    };
    checkAuth();
  }, []);

  const save = async () => {
    setIsLoading(true);
    setStatus("Signing in…");
    if (!username.trim() || !password) {
      setStatus("❌ Enter your username and password");
      setIsLoading(false);
      return;
    }

    try {
      const res = await AuthAPI.login({ username: username.trim(), password });
      if (!res?.data?.success && res?.data?.session_id) {
        localStorage.removeItem("lexecon_token");
        setChangeSession(res.data.session_id);
        setStatus("Set a new password to continue.");
        return;
      }
      if (!res?.data?.success || !res?.data?.session_id) {
        setStatus(`❌ ${res?.data?.error || "Sign in failed"}`);
        return;
      }
      localStorage.setItem("lexecon_token", res.data.session_id);
      localStorage.setItem("lexecon_tenant_id", "default");
      setStatus(`✅ Signed in as ${res.data.user?.username || username.trim()}`);
      setTimeout(() => { window.location.href = "/audit"; }, 500);
    } catch (e) {
      setStatus(`❌ ${e.message || "Sign in failed"}`);
      localStorage.removeItem("lexecon_token");
    } finally {
      setPassword("");
      setIsLoading(false);
    }
  };

  const changePassword = async () => {
    if (!password || !newPassword || newPassword !== confirmPassword) {
      setStatus("❌ Enter your current password and matching new passwords");
      return;
    }
    setIsLoading(true);
    setStatus("Changing password…");
    try {
      await AuthAPI.changePassword(changeSession, password, newPassword);
      const res = await AuthAPI.login({ username: username.trim(), password: newPassword });
      if (!res?.data?.success || !res?.data?.session_id) {
        setChangeSession("");
        setStatus("Password changed. Sign in with your new password.");
        return;
      }
      localStorage.setItem("lexecon_token", res.data.session_id);
      localStorage.setItem("lexecon_tenant_id", "default");
      setStatus("✅ Password changed. Signing in…");
      setTimeout(() => { window.location.href = "/audit"; }, 500);
    } catch (e) {
      setStatus(`❌ ${e.message || "Password change failed"}`);
    } finally {
      setPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setIsLoading(false);
    }
  };

  const isSuccess = status.startsWith("✅");
  const isError = status.startsWith("❌");

  const submit = (event) => {
    event.preventDefault();
    if (changeSession) changePassword();
    else save();
  };

  return (
    <main className="stipple-login">
      <div className="stipple-login-shell">
        <section className="stipple-login-story" aria-label="About Lexecon">
          <div className="stipple-brand">lexecon<span>.</span></div>
          <div>
            <div className="stipple-eyebrow">Local policy workspace</div>
            <h1>Decisions you can trace.</h1>
            <p>Evaluate a policy, inspect the outcome, and follow its evidence through the ledger.</p>
          </div>
          <footer>POLICY → DECISION → EVIDENCE</footer>
        </section>

        <section className="stipple-login-form-side" aria-label="Workspace sign in">
          <div className="stipple-login-top"><ThemeToggle /></div>
          <div className="stipple-eyebrow">Local access</div>
          <h2>{changeSession ? 'Change your password' : 'Open your workspace'}</h2>
          <p className="stipple-login-intro">
            {changeSession
              ? 'Choose a new password before entering the workspace.'
              : 'Sign in with the administrator account created on this machine. This prototype supports one shared organization.'}
          </p>

          {apiStatus === "offline" && (
            <div role="alert" className="stipple-notice stipple-notice-error">
              The local API is offline. From the repository root, run <code>python3 scripts/start-local.py</code>, then{' '}
              <button type="button" onClick={checkApi}>Retry connection</button>.
            </div>
          )}
          {apiStatus === "checking" && <p role="status" className="stipple-notice">Checking the local API…</p>}

          <form onSubmit={submit}>
            <label className="stipple-field" htmlFor="login-username">
              <span>Username</span>
              <input id="login-username" value={username} onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" placeholder="Your username" />
            </label>
            <label className="stipple-field" htmlFor="login-password">
              <span>{changeSession ? 'Current password' : 'Password'}</span>
              <input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" placeholder="Your password" />
            </label>
            {changeSession && (
              <>
                <label className="stipple-field" htmlFor="new-password">
                  <span>New password</span>
                  <input id="new-password" type="password" value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
                </label>
                <label className="stipple-field" htmlFor="confirm-password">
                  <span>Confirm new password</span>
                  <input id="confirm-password" type="password" value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)} autoComplete="new-password" />
                </label>
              </>
            )}
            <button className="stipple-button stipple-button-primary stipple-login-submit" type="submit" disabled={isLoading}>
              {isLoading ? 'Working…' : changeSession ? 'Change Password' : 'Sign In'}
            </button>
            {changeSession && (
              <button className="stipple-button stipple-button-quiet stipple-login-submit" type="button" onClick={() => {
                setChangeSession(""); setPassword(""); setNewPassword(""); setConfirmPassword(""); setStatus("");
              }}>Back to sign in</button>
            )}
          </form>
          {status && (
            <p role={isError ? 'alert' : 'status'} className={`stipple-notice ${isError ? 'stipple-notice-error' : isSuccess ? 'stipple-notice-success' : ''}`} style={{ marginTop: 16 }}>
              {status.replace(/^[✅❌]\s*/, '')}
            </p>
          )}
          <p className="stipple-login-footnote">Runs against the loopback API on this machine. Keep the terminal open while using the workspace.</p>
        </section>
      </div>
    </main>
  );
}
