import React, { useState, useEffect } from "react";
import { AuthAPI } from "../api/endpoints";
import { ThemeToggle } from "../contexts/ThemeContext";

export default function Login() {
  const [token, setToken] = useState(localStorage.getItem("lexecon_token") || "");
  const [tenantId, setTenantId] = useState(
    localStorage.getItem("lexecon_tenant_id") ||
      process.env.REACT_APP_DEFAULT_TENANT_ID ||
      "default"
  );
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
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
    setStatus("Validating…");

    const trimmedToken = token.trim();
    if (!trimmedToken) {
      setStatus("❌ Please enter a token");
      setIsLoading(false);
      return;
    }

    localStorage.setItem("lexecon_token", trimmedToken);
    localStorage.setItem("lexecon_tenant_id", tenantId.trim() || "default");

    try {
      const res = await AuthAPI.me();
      setStatus(`✅ Auth OK: ${res?.data?.user?.email || res?.data?.user?.username || "user"}`);
      setTimeout(() => { window.location.href = "/audit"; }, 500);
    } catch (e) {
      setStatus(`❌ Auth failed: ${e.message}`);
      localStorage.removeItem("lexecon_token");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") save();
  };

  const isSuccess = status.startsWith("✅");
  const isError = status.startsWith("❌");

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--bg-primary)",
      color: "var(--text-primary)",
      padding: 24,
    }}>
      <div style={{
        width: "100%",
        maxWidth: 440,
        padding: 36,
        borderRadius: 16,
        border: "1px solid var(--border)",
        background: "var(--bg-elevated)",
        boxShadow: "var(--shadow-lg)",
      }}>
        {/* Header row: logo + theme toggle */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: "var(--brand-primary)", display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 18,
            }}>⚖️</div>
            <h2 style={{ fontSize: "1.375rem", fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
              Lexecon
            </h2>
          </div>
          <ThemeToggle />
        </div>

        <p style={{ color: "var(--text-tertiary)", marginBottom: 24, fontSize: "0.875rem", lineHeight: 1.5 }}>
          Paste your <code style={{ background: "var(--bg-tertiary)", padding: "2px 6px", borderRadius: 4, fontSize: "0.8125rem" }}>/auth/login</code> session_id to authenticate.
        </p>

        {/* Tenant ID */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500, color: "var(--text-secondary)" }}>
            Tenant ID
          </label>
          <input
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="default"
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 8,
              border: "1px solid var(--border)", fontSize: "0.875rem",
              background: "var(--bg-secondary)", color: "var(--text-primary)",
              boxSizing: "border-box",
              transition: "border-color 200ms cubic-bezier(0.4,0,0.2,1)",
            }}
            onFocus={(e) => { e.target.style.borderColor = "var(--brand-primary)"; }}
            onBlur={(e) => { e.target.style.borderColor = "var(--border)"; }}
          />
        </div>

        {/* Token */}
        <div style={{ marginBottom: 24 }}>
          <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500, color: "var(--text-secondary)" }}>
            Token (session_id)
          </label>
          <textarea
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Paste session_id here…"
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 8,
              border: "1px solid var(--border)", fontSize: "0.875rem",
              minHeight: 100, boxSizing: "border-box",
              fontFamily: "monospace",
              background: "var(--bg-secondary)", color: "var(--text-primary)",
              resize: "vertical",
              transition: "border-color 200ms cubic-bezier(0.4,0,0.2,1)",
            }}
            onFocus={(e) => { e.target.style.borderColor = "var(--brand-primary)"; }}
            onBlur={(e) => { e.target.style.borderColor = "var(--border)"; }}
          />
        </div>

        {/* Submit */}
        <button
          onClick={save}
          disabled={isLoading}
          style={{
            width: "100%", padding: "12px 16px", borderRadius: 8,
            border: "none",
            background: isLoading ? "var(--bg-tertiary)" : "var(--brand-primary)",
            color: isLoading ? "var(--text-tertiary)" : "#fff",
            fontSize: "0.9375rem", fontWeight: 600, cursor: isLoading ? "not-allowed" : "pointer",
            transition: "all 200ms cubic-bezier(0.4,0,0.2,1)",
          }}
          onMouseEnter={(e) => { if (!isLoading) e.target.style.transform = "translateY(-1px)"; }}
          onMouseLeave={(e) => { e.target.style.transform = "translateY(0)"; }}
        >
          {isLoading ? "Validating…" : "Sign In"}
        </button>

        {/* Status */}
        {status && (
          <div style={{
            marginTop: 16, padding: "10px 14px", borderRadius: 8,
            border: `1px solid ${isSuccess ? "var(--success)" : isError ? "var(--error)" : "var(--border)"}`,
            background: isSuccess ? "var(--success-subtle)" : isError ? "var(--error-subtle)" : "var(--bg-tertiary)",
            color: isSuccess ? "var(--success-text)" : isError ? "var(--error-text)" : "var(--text-primary)",
            fontSize: "0.875rem",
          }}>
            {status}
          </div>
        )}

        {/* Help */}
        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <p style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", margin: 0, fontWeight: 600 }}>
            How to get a token
          </p>
          <ol style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.8 }}>
            <li>Run <code style={{ background: "var(--bg-tertiary)", padding: "1px 5px", borderRadius: 3 }}>curl -X POST http://localhost:8000/auth/login</code></li>
            <li>Copy the <code style={{ background: "var(--bg-tertiary)", padding: "1px 5px", borderRadius: 3 }}>session_id</code> from the response</li>
            <li>Paste it above and click Sign In</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
