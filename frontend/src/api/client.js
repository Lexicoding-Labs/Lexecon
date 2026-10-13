import axios from "axios";

const baseURL = process.env.REACT_APP_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

export const api = axios.create({
  baseURL,
  timeout: 20000,
});

// Centralized auth + tenant headers
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lexecon_token");
  const tenantId =
    localStorage.getItem("lexecon_tenant_id") ||
    process.env.REACT_APP_DEFAULT_TENANT_ID ||
    "default";

  config.headers = config.headers || {};
  config.headers["X-Tenant-ID"] = tenantId;

  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail || err?.response?.data?.message;
    const message = !err?.response
      ? `Cannot reach the Lexecon API at ${baseURL}. Start the local workspace with python3 scripts/start-local.py, then retry.`
      : typeof detail === 'string' ? detail
      : status === 403 ? 'Your account cannot perform this action.'
      : status === 500 ? 'The API could not complete this action. Check the API terminal for details.'
      : err?.message || 'Request failed';

    // Auto-logout on auth failures
    if (status === 401) {
      localStorage.removeItem("lexecon_token");
      // Only redirect if not already on login page
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }

    return Promise.reject({ status, message, raw: err });
  }
);
