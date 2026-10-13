import { api } from "./client";

// Auth endpoints
export const AuthAPI = {
  health: () => api.get("/health"),
  me: () => api.get("/auth/me"),
  login: (credentials) => api.post("/auth/login", credentials),
  changePassword: (sessionId, oldPassword, newPassword) => api.post(
    "/auth/change-password",
    { old_password: oldPassword, new_password: newPassword },
    { headers: { Authorization: `Bearer ${sessionId}` } },
  ),
  logout: () => api.post("/auth/logout"),
};

// Ledger endpoints
export const LedgerAPI = {
  listEntries: (params = {}) => api.get("/ledger/entries", { params }),
  getEntry: (id) => api.get(`/ledger/entries?event_type=${id}`), // Using filter since no direct get by id
  verify: (params = {}) => api.get("/ledger/verify", { params }),
  report: () => api.get("/ledger/report"),
};

// Demo/seed endpoint
export const DemoAPI = {
  seed: () => api.post("/demo/seed"),
};

// Compliance endpoints
export const ComplianceAPI = {
  getArticle12Status: () => api.get("/compliance/eu-ai-act/article-12/status"),
  getAuditPacket: (timeWindow = "all") => 
    api.get(`/compliance/eu-ai-act/audit-packet?time_window=${timeWindow}`),
};

// Decision endpoints
export const DecisionAPI = {
  decide: (request) => api.post("/decide", request),
  verify: (decisionResponse) => api.post("/decide/verify", decisionResponse),
};

export const PolicyAPI = {
  status: () => api.get("/policies"),
  load: (policy) => api.post("/policies/load", { policy }),
};

// Evidence export endpoint
export const EvidenceAPI = {
  export: (params = {}) => api.post("/evidence/export", params, {
    responseType: 'blob',  // Important for ZIP download
  }),
};

// Usage tracking endpoint
export const UsageAPI = {
  get: () => api.get("/usage"),
};
