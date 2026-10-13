// Raw ledger entry as returned from the API
export interface LedgerEntry {
  entry_id: string;
  event_type?: string;
  timestamp: string;
  entry_hash?: string;
  previous_hash?: string;
  data: {
    decision_id?: string;
    request_id?: string;
    action?: string;
    proposed_action?: string;
    actor?: string;
    user_id?: string;
    decision?: string;
    risk_level?: string | number;
    riskLevel?: string | number;
    policy_version_hash?: string;
    demo_origin?: string | null;
    evaluation_source?: string;
    demo_requested?: boolean;
    timestamp?: string;
    [key: string]: unknown;
  };
}

// Transformed decision used by the dashboard
export interface Decision {
  [key: string]: unknown;
  id: string;
  timestamp: string;
  action: string;
  actor: string;
  riskLevel: RiskLevel;
  outcome: Outcome;
  signature: string;
  policyVersion: string;
  verified: boolean;
  raw: LedgerEntry;
}

export type RiskLevel = 'minimal' | 'low' | 'medium' | 'high' | 'critical';
export type Outcome = 'approved' | 'denied' | 'escalated' | 'override' | 'pending';

export interface VerifyFailure {
  entry_id: string;
  reason?: string;
}

export interface VerifyResponse {
  valid?: boolean;
  verified?: boolean;
  error?: string;
  entry_id?: string;
  entries_checked?: number;
  checked_count?: number;
  failed_count?: number;
  failures?: VerifyFailure[];
}

export interface UsageData {
  decisions: {
    today: number;
    limit: number;
    remaining: number;
  };
  exports: {
    this_month: number;
    limit: number;
    remaining: number;
  };
}

export interface ExportEntry {
  id: string;
  createdAt: string;
  dateRange: string;
  format: string;
  size: string;
  status: 'ready' | 'processing';
  entries: number;
}

export interface DashboardFilters {
  search: string;
  riskLevel: string;
  outcome: string;
  dateRange: string;
  verified: boolean;
}
