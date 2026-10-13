/**
 * Lexecon decision workspace
 *
 * Replaces AuditDashboard.jsx with:
 *   • Enterprise Table component (sticky header, sorting, density, keyboard nav)
 *   • Loading skeletons while data fetches
 *   • Actionable empty states
 *   • Dark-mode-aware via CSS custom properties
 *   • Full type safety via governance.types
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Table } from '../../design-system/components/Table/Table';
import type { TableColumn } from '../../design-system/components/Table/Table';
import { ThemeToggle } from '../../contexts/ThemeContext';
import SlideOver from '../../design-system/SlideOver';
import DecisionDrilldown from '../DecisionDrilldown';
import GuidedExample from '../GuidedExample';
import { Alert } from '../../design-system/lexecon-components';
import { AuthAPI, LedgerAPI, EvidenceAPI, UsageAPI } from '../../api/endpoints';
import { formatLedgerTime, parseLedgerTime } from '../../utils/ledgerTime';

import type {
  LedgerEntry,
  Decision,
  RiskLevel,
  Outcome,
  VerifyResponse,
  UsageData,
  DashboardFilters,
} from '../../types';

// ─── Helpers ──────────────────────────────────────────────

const OUTCOME_MAP: Record<string, Outcome> = {
  allow: 'approved', permit: 'approved', allowed: 'approved',
  deny: 'denied', denied: 'denied',
  escalate: 'escalated', escalated: 'escalated',
  override: 'override',
};

function inferRisk(raw: string | number | undefined): RiskLevel {
  if (typeof raw === 'number') {
    if (raw >= 4) return 'critical';
    if (raw >= 3) return 'high';
    if (raw >= 2) return 'medium';
    return 'low';
  }
  const s = String(raw).toLowerCase();
  if (['minimal','low','medium','high','critical'].includes(s)) return s as RiskLevel;
  return 'low';
}

function decisionOrigin(data: LedgerEntry['data']): string {
  if (data.evaluation_source === 'synthetic_seed' || data.demo_origin === 'synthetic_seed_no_policy_evaluation') return 'Synthetic seed';
  if (data.evaluation_source === 'policy_engine') return data.demo_requested ? 'Policy decision · demo-tagged' : 'Policy decision';
  return data.demo_origin === 'guided_local_example' ? 'Policy decision · legacy demo tag' : 'Legacy entry';
}

function transformEntry(entry: LedgerEntry): Decision {
  const d = entry.data || {};
  return {
    id: (d.decision_id || entry.entry_id || 'UNKNOWN').toUpperCase(),
    timestamp: formatLedgerTime(entry.timestamp),
    action: String(d.action || d.proposed_action || d.event_type || entry.event_type || 'unknown'),
    actor: d.actor || d.user_id || 'system',
    riskLevel: inferRisk(d.risk_level ?? d.riskLevel),
    outcome: OUTCOME_MAP[d.decision || ''] || (d.decision as Outcome) || 'pending',
    signature: (entry.entry_hash || '').substring(0, 64) || 'unknown',
    policyVersion: d.policy_version_hash ? `v${d.policy_version_hash.substring(0, 7)}` : 'unknown',
    verified: false,
    raw: entry,
  };
}

// ─── Main Component ───────────────────────────────────────

export default function AuditDashboard() {
  const [activeTab, setActiveTab] = useState('ledger');
  const [filters, setFilters] = useState<DashboardFilters>({
    search: '', riskLevel: 'all', outcome: 'all', dateRange: '7days', verified: false,
  });
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [totalCount, setTotalCount] = useState(0);

  const [verifyStatus, setVerifyStatus] = useState<VerifyResponse | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [lastVerifiedAt, setLastVerifiedAt] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState('');

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<LedgerEntry | null>(null);
  const closeDrawer = useCallback(() => { setDrawerOpen(false); setSelectedEntry(null); }, []);

  const [usage, setUsage] = useState<UsageData | null>(null);

  // ── Load ──
  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await LedgerAPI.listEntries({ event_type: 'decision', limit: 200 });
      const entries: LedgerEntry[] = res.data?.entries || [];
      setTotalCount(res.data?.total || entries.length);
      setDecisions(entries.map(transformEntry));
      setVerifyStatus(null);
      setLastVerifiedAt(null);
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || 'Failed to load ledger events');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUsage = useCallback(async () => {
    try {
      const res = await UsageAPI.get();
      setUsage(res.data);
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { loadEvents(); loadUsage(); }, [loadEvents, loadUsage]);

  // ── Verify ──
  const runVerification = useCallback(async () => {
    setVerifying(true);
    setError('');
    setVerifyStatus(null);
    setLastVerifiedAt(null);
    try {
      const res = await LedgerAPI.verify({ limit: 1000 });
      setVerifyStatus(res.data);
      setLastVerifiedAt(new Date().toISOString());
    } catch (e: unknown) {
      setError(`Integrity check could not complete: ${(e as { message?: string })?.message || 'request failed'}. Select Verify Integrity to retry.`);
    } finally {
      setVerifying(false);
    }
  }, []);

  const exportEvidence = useCallback(async () => {
    setError('');
    setExportStatus('');
    try {
      const result = await EvidenceAPI.export({ include_verification: true });
      const url = window.URL.createObjectURL(result.data);
      const link = document.createElement('a');
      link.href = url;
      const filename = `lexecon-evidence-${new Date().toISOString().slice(0, 10)}.zip`;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setExportStatus(`Evidence download started: ${filename}`);
      loadUsage();
      // Keep the object URL alive long enough for the browser to begin saving.
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || 'Evidence export failed');
    }
  }, [loadUsage]);

  const signOut = useCallback(async () => {
    try { await AuthAPI.logout(); } catch { /* remove the local session even if the API is offline */ }
    localStorage.removeItem('lexecon_token');
    localStorage.removeItem('lexecon_tenant_id');
    window.location.replace('/login');
  }, []);

  // ── Filtered data ──
  const verifiedAll = Boolean(verifyStatus?.valid || verifyStatus?.verified);
  const filtered = decisions.filter((d) => {
    const days = ({ '24hours': 1, '7days': 7, '30days': 30 } as Record<string, number>)[filters.dateRange];
    if (days && parseLedgerTime(d.raw.timestamp) < Date.now() - days * 86_400_000) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      if (!d.action.toLowerCase().includes(q) && !d.id.toLowerCase().includes(q)) return false;
    }
    if (filters.riskLevel !== 'all' && d.riskLevel !== filters.riskLevel) return false;
    if (filters.outcome !== 'all' && d.outcome !== filters.outcome) return false;
    if (filters.verified && !verifiedAll) return false;
    return true;
  }).map((d) => ({ ...d, verified: verifiedAll }));

  // ── Table columns ──
  const columns: TableColumn<Decision>[] = [
    {
      key: 'id', header: 'Decision ID', sortable: true, width: '130px',
      render: (val) => (
        <span className="stipple-decision-id" title={String(val)}>
          {String(val)}
        </span>
      ),
    },
    {
      key: 'timestamp', header: 'Timestamp', sortable: true, width: '180px',
      render: (val) => (
        <span style={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
          {String(val)}
        </span>
      ),
    },
    {
      key: 'action', header: 'Action', sortable: true,
      render: (val, row) => (
        <div>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{String(val)}</span>
          <br />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>by {(row as Decision).actor}</span>
          <span className="stipple-mobile-row-meta">
            {decisionOrigin((row as Decision).raw.data)}<br />
            Ledger: {(row as Decision).verified ? 'passed' : verifyStatus?.valid === false ? 'failed' : 'not checked'}
          </span>
        </div>
      ),
    },
    {
      key: 'riskLevel', header: 'Risk', sortable: true, width: '90px',
      render: (val) => (
        <span className="stipple-risk">{String(val)}</span>
      ),
    },
    {
      key: 'outcome', header: 'Outcome', sortable: true, width: '110px',
      render: (val) => (
        <span className={`stipple-outcome stipple-outcome--${String(val)}`}>{String(val)}</span>
      ),
    },
    {
      key: 'raw', header: 'Origin', width: '160px',
      render: (_val, row) => {
        return <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {decisionOrigin((row as Decision).raw.data)}
        </span>;
      },
    },
    {
      key: 'verified', header: 'Ledger check', width: '150px',
      render: (val) => (
        <span style={{ color: val ? 'var(--success-text)' : verifyStatus?.valid === false ? 'var(--error-text)' : 'var(--text-tertiary)', fontSize: '0.8rem', fontWeight: 600 }}>
          {val ? '✓ Passed' : verifyStatus?.valid === false ? 'Failed' : 'Not checked'}
        </span>
      ),
    },
  ];

  const tabs = [
    { id: 'ledger', label: 'Ledger' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'analytics', label: 'Analytics' },
    { id: 'exports', label: 'Exports' },
  ];
  const chainPassed = Boolean(verifyStatus?.valid || verifyStatus?.verified);

  return (
    <div className="stipple-workspace">
      <header className="stipple-appbar">
        <div className="stipple-appbar-inner">
          <div className="stipple-appbar-left">
            <span className="stipple-brand">lexecon<span>.</span></span>
            <span className="stipple-appbar-label">Local workspace</span>
          </div>
          <div className="stipple-appbar-right"><ThemeToggle /><button type="button" className="stipple-button stipple-button-quiet" onClick={signOut}>Sign out</button></div>
        </div>
      </header>

      <main className="stipple-workspace-main">
        <section className="stipple-page-head" aria-label="Decision workspace">
          <div>
            <div className="stipple-eyebrow">Policy / evidence</div>
            <h1>Decisions</h1>
            <p>Policy outcomes and ledger evidence from this local workspace.</p>
          </div>
          <div className="stipple-page-actions">
            {verifyStatus && <span role="status" className={`stipple-verified ${chainPassed ? '' : 'stipple-verified-failed'}`}>
              {chainPassed ? `CHAIN PASSED (${verifyStatus.entries_checked || verifyStatus.checked_count || 0})` : 'CHAIN FAILED'}
            </span>}
            <button type="button" className="stipple-button" onClick={runVerification} disabled={verifying}>
              {verifying ? 'Verifying…' : 'Verify Integrity'}
            </button>
            <button type="button" className="stipple-button stipple-button-primary" onClick={exportEvidence}>Export Audit</button>
          </div>
        </section>

        <StatusStrip totalDecisions={totalCount} loading={loading} checked={verifyStatus !== null}
          passed={chainPassed} lastVerifiedAt={lastVerifiedAt} onRefresh={loadEvents} />
        {exportStatus && <p role="status" className="stipple-status-note">{exportStatus}</p>}
        {error && <div role="alert" className="stipple-notice stipple-notice-error">
          <strong>Action failed:</strong> {error}{' '}
          <button type="button" onClick={loadEvents}>Retry loading decisions</button>
        </div>}
        <GuidedExample onComplete={async () => { await Promise.all([loadEvents(), loadUsage()]); }} />

        {verifyStatus && !chainPassed && (
          <div role="alert" className="stipple-notice stipple-notice-error">
            <strong>Integrity failures detected.</strong>{' '}{verifyStatus.error || 'The ledger check did not pass.'}
            {verifyStatus.entry_id && ` Entry: ${verifyStatus.entry_id}.`}
            {verifyStatus.failures && verifyStatus.failures.length > 0 && (
              <ul style={{ margin: '8px 0 0 18px' }}>
                {verifyStatus.failures.slice(0, 10).map((f, i) => <li key={i}>{f.entry_id}: {f.reason || 'Hash mismatch'}</li>)}
              </ul>
            )}
          </div>
        )}

        <nav className="stipple-tabs" role="tablist" aria-label="Decision views">
          {tabs.map((tab, index) => (
            <button key={tab.id} type="button" role="tab" className="stipple-tab"
              id={`stipple-tab-${tab.id}`} aria-selected={activeTab === tab.id}
              aria-controls={`stipple-panel-${tab.id}`} tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
                event.preventDefault();
                const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
                setActiveTab(tabs[next].id);
                document.getElementById(`stipple-tab-${tabs[next].id}`)?.focus();
              }}>
              {tab.label}
            </button>
          ))}
        </nav>
        <section role="tabpanel" id={`stipple-panel-${activeTab}`} aria-labelledby={`stipple-tab-${activeTab}`}>
          {activeTab === 'ledger' && (
            <LedgerTab filters={filters} onFiltersChange={setFilters} data={filtered} columns={columns}
              loading={loading} error={error}
              onRowClick={(row) => { setSelectedEntry(row.raw); setDrawerOpen(true); }} />
          )}
          {activeTab === 'timeline' && <TimelineTab decisions={filtered} />}
          {activeTab === 'analytics' && <AnalyticsTab decisions={filtered} />}
          {activeTab === 'exports' && <ExportsTab />}
        </section>
        {usage && <UsageLine usage={usage} onRefresh={loadUsage} />}
      </main>

      <SlideOver open={drawerOpen} title="Decision details" onClose={closeDrawer}>
        <DecisionDrilldown entry={selectedEntry} verification={verifyStatus?.valid === true ? 'passed' : verifyStatus?.valid === false ? 'failed' : 'unchecked'} />
      </SlideOver>
    </div>
  );
}

// ─── Compact workspace status ─────────────────────────────

function StatusStrip({ totalDecisions, loading, checked, passed, lastVerifiedAt, onRefresh }: {
  totalDecisions: number; loading: boolean; checked: boolean; passed: boolean;
  lastVerifiedAt: string | null; onRefresh: () => void;
}) {
  return (
    <div className="stipple-meta-line">
      <span><strong>{loading ? '…' : totalDecisions.toLocaleString()}</strong> decision entries</span>
      <span>Ledger: <strong>{checked ? (passed ? 'Passed' : 'Failed') : 'Not checked'}</strong></span>
      {lastVerifiedAt && <span>Last verified: {new Date(lastVerifiedAt).toLocaleString()}</span>}
      <button type="button" className="stipple-button stipple-button-quiet" onClick={onRefresh} disabled={loading}>
        {loading ? 'Loading…' : 'Refresh ledger'}
      </button>
    </div>
  );
}

function UsageLine({ usage, onRefresh }: { usage: UsageData; onRefresh: () => void }) {
  return (
    <p className="stipple-usage">
      Local usage: <strong>{usage.decisions.today} / {usage.decisions.limit}</strong> decisions today ·{' '}
      <strong>{usage.exports.this_month} / {usage.exports.limit}</strong> exports this month ·{' '}
      <button type="button" className="stipple-button stipple-button-quiet" onClick={onRefresh}>Refresh usage</button>
    </p>
  );
}

// ─── Ledger Tab ───────────────────────────────────────────

function LedgerTab({
  filters, onFiltersChange, data, columns, loading, error, onRowClick
}: {
  filters: DashboardFilters;
  onFiltersChange: (f: DashboardFilters) => void;
  data: Decision[];
  columns: TableColumn<Decision>[];
  loading: boolean;
  error: string;
  onRowClick: (row: Decision) => void;
}) {
  return (
    <div>
      <div className="stipple-filterbar" aria-label="Ledger filters">
        <label className="stipple-filter" htmlFor="ledger-search">
          <span>Search</span>
          <input id="ledger-search" type="search" placeholder="Action or decision ID"
            value={filters.search}
            onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })} />
        </label>
        <label className="stipple-filter" htmlFor="ledger-risk">
          <span>Risk</span>
          <select id="ledger-risk" value={filters.riskLevel}
            onChange={(e) => onFiltersChange({ ...filters, riskLevel: e.target.value })}>
            <option value="all">All levels</option><option value="minimal">Minimal</option>
            <option value="low">Low</option><option value="medium">Medium</option>
            <option value="high">High</option><option value="critical">Critical</option>
          </select>
        </label>
        <label className="stipple-filter" htmlFor="ledger-outcome">
          <span>Outcome</span>
          <select id="ledger-outcome" value={filters.outcome}
            onChange={(e) => onFiltersChange({ ...filters, outcome: e.target.value })}>
            <option value="all">All outcomes</option><option value="approved">Approved</option>
            <option value="denied">Denied</option><option value="escalated">Escalated</option>
            <option value="override">Override</option>
          </select>
        </label>
        <label className="stipple-filter" htmlFor="ledger-range">
          <span>Date range</span>
          <select id="ledger-range" value={filters.dateRange}
            onChange={(e) => onFiltersChange({ ...filters, dateRange: e.target.value })}>
            <option value="24hours">Last 24 hours</option><option value="7days">Last 7 days</option>
            <option value="30days">Last 30 days</option><option value="all">All time</option>
          </select>
        </label>
        <label className="stipple-filter-check">
          <input type="checkbox" checked={filters.verified}
            onChange={(e) => onFiltersChange({ ...filters, verified: e.target.checked })} />
          Checked only
        </label>
      </div>
      {!loading && !error && <p className="stipple-table-count">{data.length} matching decision {data.length === 1 ? 'entry' : 'entries'} · Select a row to inspect its evidence.</p>}
      <Table<Decision> className="stipple-ledger-table" columns={columns} data={data} loading={loading}
        rowIdKey="id" defaultSortKey="timestamp" defaultSortDir="desc" onRowClick={onRowClick}
        emptyIcon="" emptyTitle="No ledger entries found"
        emptyDescription="Run the policy example above or adjust your filters." />
    </div>
  );
}

// ─── Timeline Tab ─────────────────────────────────────────

function TimelineTab({ decisions }: { decisions: Decision[] }) {
  const entries = [...decisions].sort((a, b) => parseLedgerTime(b.raw.timestamp) - parseLedgerTime(a.raw.timestamp));
  const dotColor: Record<Outcome, string> = {
    approved: 'var(--success)', denied: 'var(--error)', escalated: 'var(--warning)',
    override: 'var(--brand-primary)', pending: 'var(--text-tertiary)',
  };

  return (
    <div>
      <Alert variant="info">{entries.length} decision events from the current ledger view.</Alert>

      <div style={{
        marginTop: 16, padding: 24, borderRadius: 12,
        border: '1px solid var(--border)', background: 'var(--bg-elevated)',
      }}>
        {entries.length === 0 && <p>No decision events yet. Run the policy example to explore the workflow.</p>}
        {entries.map((e, i) => (
          <div key={e.id} style={{ display: 'flex', gap: 16, animation: `fadeIn ${200 + i * 100}ms cubic-bezier(0.4,0,0.2,1) both` }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: dotColor[e.outcome] }} />
              {i < entries.length - 1 && <div style={{ width: 2, flex: 1, marginTop: 4, background: 'var(--border)' }} />}
            </div>
            <div style={{ flex: 1, paddingBottom: i < entries.length - 1 ? 24 : 0 }}>
              <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-tertiary)' }}>{e.timestamp}</span>
              <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: '4px 0 4px' }}>{e.action}</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: 0 }}>{e.outcome} · {e.actor}</p>
              <code style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', display: 'block', marginTop: 6 }}>
                Entry hash: {e.signature.substring(0, 12)}…
              </code>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Analytics Tab ────────────────────────────────────────

function AnalyticsTab({ decisions }: { decisions: Decision[] }) {
  const counts = decisions.reduce<Record<Outcome, number>>((acc, decision) => {
    acc[decision.outcome] += 1;
    return acc;
  }, { approved: 0, denied: 0, escalated: 0, override: 0, pending: 0 });
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
      <div style={{
          borderRadius: 12, border: '1px solid var(--border)', background: 'var(--bg-elevated)', overflow: 'hidden',
        }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
            <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Decision outcomes</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>Current loaded ledger view ({decisions.length} entries)</p>
          </div>
          <div style={{ padding: 20 }}>
            {Object.entries(counts).map(([outcome, count]) => (
              <p key={outcome} style={{ display: 'flex', justifyContent: 'space-between', margin: '6px 0' }}>
                <span style={{ textTransform: 'capitalize' }}>{outcome}</span><strong>{count}</strong>
              </p>
            ))}
          </div>
        </div>
    </div>
  );
}

// ─── Exports Tab ──────────────────────────────────────────

function ExportsTab() {
  return (
    <div>
      <Alert variant="info">
        The API can create a signed evidence ZIP. Export history is not connected to this dashboard yet.
      </Alert>
    </div>
  );
}
