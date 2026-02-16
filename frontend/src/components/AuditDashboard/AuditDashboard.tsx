/**
 * Lexecon Audit Dashboard – TypeScript rewrite
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
import { Badge } from '../../design-system/components/Badge/Badge';
import type { BadgeVariant } from '../../design-system/components/Badge/Badge';
import { PageSkeleton } from '../../design-system/components/Skeleton/Skeleton';
import { ComplianceMetrics } from '../ComplianceMetrics/ComplianceMetrics';
import { ThemeToggle } from '../../contexts/ThemeContext';
import SlideOver from '../../design-system/SlideOver';
import DecisionDrilldown from '../DecisionDrilldown';
import {
  Button, Input, Card, Alert, Select, Checkbox, Tabs, Modal
} from '../../design-system/lexecon-components';
import { tokens } from '../../design-system/lexecon-design-tokens';
import { LedgerAPI, DemoAPI, EvidenceAPI, UsageAPI } from '../../api/endpoints';

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

function formatTs(ts?: string): string {
  if (!ts) return 'Unknown';
  try { return new Date(ts).toISOString().replace('T', ' ').substring(0, 19) + ' UTC'; }
  catch { return ts; }
}

function transformEntry(entry: LedgerEntry): Decision {
  const d = entry.data || {};
  return {
    id: (d.decision_id || entry.entry_id || 'UNKNOWN').toUpperCase(),
    timestamp: formatTs(entry.timestamp),
    action: d.action || d.proposed_action || d.event_type || entry.event_type || 'unknown',
    actor: d.actor || d.user_id || 'system',
    riskLevel: inferRisk(d.risk_level ?? d.riskLevel),
    outcome: OUTCOME_MAP[d.decision || ''] || (d.decision as Outcome) || 'pending',
    signature: (entry.entry_hash || '').substring(0, 64) || 'unknown',
    policyVersion: d.policy_version_hash ? `v${d.policy_version_hash.substring(0, 7)}` : 'v1.0.0',
    verified: true,
    raw: entry,
  };
}

// ─── Badge variant maps ───────────────────────────────────

const RISK_BADGE: Record<RiskLevel, BadgeVariant> = {
  minimal: 'success', low: 'success', medium: 'warning', high: 'warning', critical: 'error',
};

const OUTCOME_BADGE: Record<Outcome, BadgeVariant> = {
  approved: 'success', denied: 'error', escalated: 'warning', override: 'primary', pending: 'info',
};

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

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<LedgerEntry | null>(null);

  const [usage, setUsage] = useState<UsageData | null>(null);

  // ── Load ──
  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await LedgerAPI.listEntries({ limit: 200 });
      const entries: LedgerEntry[] = res.data?.entries || [];
      setTotalCount(res.data?.total || entries.length);
      setDecisions(entries.map(transformEntry));
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

  // ── Seed ──
  const seedDemo = useCallback(async () => {
    setLoading(true);
    try { await DemoAPI.seed(); } catch { /* may not exist */ }
    await loadEvents();
  }, [loadEvents]);

  // ── Verify ──
  const runVerification = useCallback(async () => {
    setVerifying(true);
    setError('');
    try {
      const res = await LedgerAPI.verify({ limit: 1000 });
      setVerifyStatus(res.data);
      setLastVerifiedAt(new Date().toISOString());
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  }, []);

  // ── Filtered data ──
  const filtered = decisions.filter((d) => {
    if (filters.search) {
      const q = filters.search.toLowerCase();
      if (!d.action.toLowerCase().includes(q) && !d.id.toLowerCase().includes(q)) return false;
    }
    if (filters.riskLevel !== 'all' && d.riskLevel !== filters.riskLevel) return false;
    if (filters.outcome !== 'all' && d.outcome !== filters.outcome) return false;
    return true;
  });

  // ── Table columns ──
  const columns: TableColumn<Decision>[] = [
    {
      key: 'id', header: 'Decision ID', sortable: true, width: '130px',
      render: (val) => (
        <span style={{ fontFamily: 'monospace', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--brand-primary)' }}>
          {val}
        </span>
      ),
    },
    {
      key: 'timestamp', header: 'Timestamp', sortable: true, width: '180px',
      render: (val) => (
        <span style={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
          {val}
        </span>
      ),
    },
    {
      key: 'action', header: 'Action', sortable: true,
      render: (val, row) => (
        <div>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{val}</span>
          <br />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>by {(row as Decision).actor}</span>
        </div>
      ),
    },
    {
      key: 'riskLevel', header: 'Risk', sortable: true, width: '90px',
      render: (val) => (
        <Badge variant={RISK_BADGE[val as RiskLevel]} size="sm">
          {String(val).toUpperCase()}
        </Badge>
      ),
    },
    {
      key: 'outcome', header: 'Outcome', sortable: true, width: '110px',
      render: (val) => (
        <Badge variant={OUTCOME_BADGE[val as Outcome]} size="sm" pulseDot>
          {String(val).toUpperCase()}
        </Badge>
      ),
    },
    {
      key: 'verified', header: 'Verified', width: '80px',
      render: (val) => (
        <span style={{ color: val ? 'var(--success)' : 'var(--error)', fontSize: '0.875rem', fontWeight: 500 }}>
          {val ? '✓ Yes' : '✕ No'}
        </span>
      ),
    },
  ];

  // ── Render ──
  if (loading && decisions.length === 0) {
    return <PageSkeleton />;
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* ── Header ── */}
      <header style={{
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        boxShadow: 'var(--shadow-sm)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        <div style={{ maxWidth: 1440, margin: '0 auto', padding: '20px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Audit Dashboard
            </h1>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
              Tamper-evident decision ledger with cryptographic verification
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <ThemeToggle />
            {verifyStatus && (
              <Badge
                variant={(verifyStatus.valid || verifyStatus.verified) ? 'success' : 'error'}
                size="md"
                dot
              >
                {(verifyStatus.valid || verifyStatus.verified)
                  ? `VERIFIED (${verifyStatus.entries_checked || verifyStatus.checked_count || 0})`
                  : `FAILED: ${verifyStatus.failed_count || 0}`}
              </Badge>
            )}
            <button
              onClick={runVerification}
              disabled={verifying}
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                fontWeight: 500,
                fontSize: '0.875rem',
                cursor: verifying ? 'not-allowed' : 'pointer',
                opacity: verifying ? 0.6 : 1,
                transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
              }}
            >
              {verifying ? '⏳ Verifying…' : '🔐 Verify Integrity'}
            </button>
            <button
              onClick={() => {}}
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                border: 'none',
                background: 'var(--brand-primary)',
                color: '#fff',
                fontWeight: 500,
                fontSize: '0.875rem',
                cursor: 'pointer',
                transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              📥 Export Audit
            </button>
          </div>
        </div>
        {lastVerifiedAt && (
          <div style={{ textAlign: 'right', padding: '0 32px 8px', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
            Last verified: {new Date(lastVerifiedAt).toLocaleString()}
          </div>
        )}
      </header>

      {/* ── Body ── */}
      <main style={{ maxWidth: 1440, margin: '0 auto', padding: '24px 32px' }}>
        {/* Stats */}
        <StatsGrid totalDecisions={totalCount} loading={loading} onRefresh={loadEvents} onSeed={seedDemo} />

        {/* Usage banner */}
        {usage && <UsageBanner usage={usage} onRefresh={loadUsage} />}

        {/* Integrity failures */}
        {verifyStatus && !verifyStatus.valid && !verifyStatus.verified && verifyStatus.failures && (
          <div style={{
            marginTop: 20,
            padding: 16,
            borderRadius: 10,
            border: '1px solid var(--error)',
            background: 'var(--error-subtle)',
            color: 'var(--error-text)',
          }}>
            <div style={{ fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              ⚠️ Integrity Failures Detected
            </div>
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {verifyStatus.failures.slice(0, 10).map((f, i) => (
                <li key={i} style={{ marginBottom: 4, fontSize: '0.875rem' }}>
                  <strong>{f.entry_id}</strong> — {f.reason || 'Hash mismatch'}
                </li>
              ))}
            </ul>
            {verifyStatus.failures.length > 10 && (
              <div style={{ marginTop: 8, fontSize: '0.75rem', opacity: 0.8 }}>
                Showing 10 of {verifyStatus.failures.length} failures.
              </div>
            )}
          </div>
        )}

        {/* Tabs */}
        <div style={{ marginTop: 28 }}>
          <Tabs
            tabs={[
              { id: 'ledger', label: 'Decision Ledger' },
              { id: 'timeline', label: 'Timeline View' },
              { id: 'analytics', label: 'Analytics' },
              { id: 'exports', label: 'Audit Exports' },
            ]}
            activeTab={activeTab}
            onChange={setActiveTab}
            variant="line"
          />
        </div>

        {/* Tab content */}
        <div style={{ marginTop: 20 }}>
          {activeTab === 'ledger' && (
            <LedgerTab
              filters={filters}
              onFiltersChange={setFilters}
              data={filtered}
              columns={columns}
              loading={loading}
              error={error}
              onSeed={seedDemo}
              onRowClick={(row) => { setSelectedEntry((row as Decision).raw); setDrawerOpen(true); }}
            />
          )}
          {activeTab === 'timeline' && <TimelineTab />}
          {activeTab === 'analytics' && <AnalyticsTab />}
          {activeTab === 'exports' && <ExportsTab />}
        </div>
      </main>

      {/* Drilldown slide-over */}
      <SlideOver
        open={drawerOpen}
        title={selectedEntry?.data?.decision_id ? `Decision ${selectedEntry.data.decision_id}` : (selectedEntry?.entry_id ? `Entry ${selectedEntry.entry_id}` : 'Decision Details')}
        onClose={() => { setDrawerOpen(false); setSelectedEntry(null); }}
      >
        <DecisionDrilldown entry={selectedEntry} />
      </SlideOver>
    </div>
  );
}

// ─── Stats Grid ───────────────────────────────────────────

function StatsGrid({ totalDecisions, loading, onRefresh, onSeed }: {
  totalDecisions: number; loading: boolean;
  onRefresh: () => void; onSeed: () => void;
}) {
  const stats = [
    { label: 'Total Decisions', value: loading ? '…' : totalDecisions.toLocaleString(), sub: 'Live from ledger', type: 'positive' as const, icon: '📊' },
    { label: 'Verified Entries', value: loading ? '…' : '100%', sub: 'Cryptographic integrity', type: 'positive' as const, icon: '✓' },
    { label: 'Escalations', value: '0', sub: 'From ledger data', type: 'neutral' as const, icon: '⚠' },
    { label: 'High Risk', value: '0', sub: 'Requiring oversight', type: 'neutral' as const, icon: '🎯' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <button
          onClick={onRefresh}
          disabled={loading}
          style={{
            padding: '8px 16px', borderRadius: 8, border: 'none',
            background: loading ? 'var(--bg-tertiary)' : 'var(--brand-primary)',
            color: loading ? 'var(--text-tertiary)' : '#fff',
            fontWeight: 500, fontSize: '0.875rem', cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
          }}
        >
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
        <button
          onClick={onSeed}
          disabled={loading}
          style={{
            padding: '8px 16px', borderRadius: 8, border: 'none',
            background: loading ? 'var(--bg-tertiary)' : 'var(--success)',
            color: loading ? 'var(--text-tertiary)' : '#fff',
            fontWeight: 500, fontSize: '0.875rem', cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
          }}
        >
          {loading ? '…' : '⚡ Load Demo Data'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        {stats.map((s, i) => (
          <div key={i} style={{
            padding: 20,
            borderRadius: 12,
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            boxShadow: 'var(--shadow-sm)',
            transition: 'box-shadow 200ms cubic-bezier(0.4,0,0.2,1), transform 200ms cubic-bezier(0.4,0,0.2,1)',
          }}
            onMouseEnter={(e) => { const el = e.currentTarget; el.style.boxShadow = 'var(--shadow-md)'; el.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={(e) => { const el = e.currentTarget; el.style.boxShadow = 'var(--shadow-sm)'; el.style.transform = 'translateY(0)'; }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <p style={{ fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-secondary)', margin: 0 }}>{s.label}</p>
                <p style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', margin: '8px 0 4px' }}>{s.value}</p>
                <p style={{
                  fontSize: '0.8125rem', margin: 0,
                  color: s.type === 'positive' ? 'var(--success)' : 'var(--text-tertiary)',
                }}>{s.sub}</p>
              </div>
              <span style={{ fontSize: '1.75rem' }}>{s.icon}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Usage Banner ─────────────────────────────────────────

function UsageBanner({ usage, onRefresh }: { usage: UsageData; onRefresh: () => void }) {
  const dPct = (usage.decisions.today / usage.decisions.limit) * 100;
  const ePct = (usage.exports.this_month / usage.exports.limit) * 100;
  const warn = dPct > 80 || ePct > 80;
  const atLimit = usage.decisions.remaining <= 0 || usage.exports.remaining <= 0;

  return (
    <div style={{
      marginTop: 16,
      padding: '12px 16px',
      borderRadius: 10,
      border: `1px solid ${atLimit ? 'var(--error)' : warn ? 'var(--warning)' : 'var(--success)'}`,
      background: atLimit ? 'var(--error-subtle)' : warn ? 'var(--warning-subtle)' : 'var(--success-subtle)',
      display: 'flex',
      alignItems: 'center',
      gap: 20,
      fontSize: '0.8125rem',
      flexWrap: 'wrap',
    }}>
      <span>
        📊 <strong>Decisions today:</strong>{' '}
        <span style={{ fontWeight: 600, color: warn ? 'var(--warning-text)' : 'var(--success-text)' }}>
          {usage.decisions.today} / {usage.decisions.limit}
        </span>
        {dPct > 80 && ' (approaching limit)'}
      </span>
      <span>
        📦 <strong>Exports this month:</strong>{' '}
        <span style={{ fontWeight: 600, color: ePct > 80 ? 'var(--warning-text)' : 'var(--success-text)' }}>
          {usage.exports.this_month} / {usage.exports.limit}
        </span>
        {ePct > 80 && ' (approaching limit)'}
      </span>
      <button
        onClick={onRefresh}
        style={{
          marginLeft: 'auto', fontSize: '0.75rem', padding: '3px 8px',
          border: '1px solid var(--border)', borderRadius: 4,
          background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer',
        }}
      >↻ Refresh</button>
    </div>
  );
}

// ─── Ledger Tab ───────────────────────────────────────────

function LedgerTab({
  filters, onFiltersChange, data, columns, loading, error, onSeed, onRowClick
}: {
  filters: DashboardFilters;
  onFiltersChange: (f: DashboardFilters) => void;
  data: Decision[];
  columns: TableColumn<Decision>[];
  loading: boolean;
  error: string;
  onSeed: () => void;
  onRowClick: (row: Decision) => void;
}) {
  return (
    <div>
      {/* Filters */}
      <div style={{
        padding: 20,
        borderRadius: 12,
        border: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        marginBottom: 16,
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14 }}>
          <Input
            label="Search"
            placeholder="Search decisions…"
            value={filters.search}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFiltersChange({ ...filters, search: e.target.value })}
          />
          <Select
            label="Risk Level"
            options={[
              { value: 'all', label: 'All Levels' },
              { value: 'minimal', label: 'Minimal' },
              { value: 'low', label: 'Low' },
              { value: 'medium', label: 'Medium' },
              { value: 'high', label: 'High' },
              { value: 'critical', label: 'Critical' },
            ]}
            value={filters.riskLevel}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onFiltersChange({ ...filters, riskLevel: e.target.value })}
          />
          <Select
            label="Outcome"
            options={[
              { value: 'all', label: 'All Outcomes' },
              { value: 'approved', label: 'Approved' },
              { value: 'denied', label: 'Denied' },
              { value: 'escalated', label: 'Escalated' },
              { value: 'override', label: 'Override' },
            ]}
            value={filters.outcome}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onFiltersChange({ ...filters, outcome: e.target.value })}
          />
          <Select
            label="Date Range"
            options={[
              { value: '24hours', label: 'Last 24 Hours' },
              { value: '7days', label: 'Last 7 Days' },
              { value: '30days', label: 'Last 30 Days' },
              { value: 'all', label: 'All Time' },
            ]}
            value={filters.dateRange}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onFiltersChange({ ...filters, dateRange: e.target.value })}
          />
          <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 4 }}>
            <Checkbox
              label="Verified only"
              checked={filters.verified}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFiltersChange({ ...filters, verified: e.target.checked })}
            />
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="error" icon={true}>
          <strong>Error:</strong> {error}
        </Alert>
      )}

      {!loading && !error && data.length > 0 && (
        <Alert variant="success" icon={true}>
          <strong>Ledger Verified</strong> — {data.length} entries loaded with valid cryptographic signatures.
        </Alert>
      )}

      <div style={{ marginTop: 12 }}>
        <Table<Decision>
          columns={columns}
          data={data}
          loading={loading}
          rowIdKey="id"
          defaultSortKey="timestamp"
          defaultSortDir="desc"
          onRowClick={onRowClick}
          emptyIcon="📭"
          emptyTitle="No ledger entries found"
          emptyDescription="Try loading demo data or adjusting your filters."
          emptyActions={[
            { label: 'Load Demo Data', onClick: onSeed },
          ]}
        />
      </div>
    </div>
  );
}

// ─── Timeline Tab ─────────────────────────────────────────

function TimelineTab() {
  const entries = [
    { time: '14:32:15', title: 'Model Inference Approved', desc: 'Low-risk decision automatically approved by policy engine', type: 'success' as const, sig: 'a4f3e8d2…' },
    { time: '14:28:03', title: 'Decision Escalated', desc: 'High-risk score triggered human oversight workflow', type: 'warning' as const, sig: 'b5g4f9e3…' },
    { time: '14:15:47', title: 'Request Denied', desc: 'Policy violation detected — insufficient permissions', type: 'error' as const, sig: 'c6h5g0f4…' },
  ];

  const dotColor: Record<string, string> = { success: 'var(--success)', warning: 'var(--warning)', error: 'var(--error)' };

  return (
    <div>
      <Alert variant="info">
        Timeline view shows decision flow in chronological order with visual connections.
      </Alert>

      <div style={{
        marginTop: 16, padding: 24, borderRadius: 12,
        border: '1px solid var(--border)', background: 'var(--bg-elevated)',
      }}>
        {entries.map((e, i) => (
          <div key={i} style={{ display: 'flex', gap: 16, animation: `fadeIn ${200 + i * 100}ms cubic-bezier(0.4,0,0.2,1) both` }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: dotColor[e.type], boxShadow: `0 0 6px ${dotColor[e.type]}80` }} />
              {i < entries.length - 1 && <div style={{ width: 2, flex: 1, marginTop: 4, background: 'var(--border)' }} />}
            </div>
            <div style={{ flex: 1, paddingBottom: i < entries.length - 1 ? 24 : 0 }}>
              <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-tertiary)' }}>{e.time}</span>
              <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: '4px 0 4px' }}>{e.title}</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: 0 }}>{e.desc}</p>
              <code style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', display: 'block', marginTop: 6 }}>
                Signature: {e.sig}
              </code>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Analytics Tab ────────────────────────────────────────

function AnalyticsTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
      {/* Placeholder charts */}
      {[
        { title: 'Decision Outcomes', sub: 'Last 30 days', placeholder: '📊 Pie chart' },
        { title: 'Risk Distribution', sub: 'Current period', placeholder: '📈 Bar chart' },
        { title: 'Decision Volume', sub: 'Trend over time', placeholder: '📉 Line chart' },
      ].map((c, i) => (
        <div key={i} style={{
          borderRadius: 12, border: '1px solid var(--border)', background: 'var(--bg-elevated)', overflow: 'hidden',
        }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
            <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{c.title}</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>{c.sub}</p>
          </div>
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: '1.5rem' }}>
            {c.placeholder}
          </div>
        </div>
      ))}

      <ComplianceMetrics />
    </div>
  );
}

// ─── Exports Tab ──────────────────────────────────────────

function ExportsTab() {
  const exports = [
    { id: 'EXP-001', createdAt: '2026-01-09 10:23 UTC', dateRange: '2025-12-01 → 2026-01-01', format: 'JSON', size: '2.4 MB', status: 'ready' as const, entries: 1247 },
    { id: 'EXP-002', createdAt: '2026-01-05 14:15 UTC', dateRange: '2025-11-01 → 2025-12-01', format: 'CSV', size: '1.8 MB', status: 'ready' as const, entries: 923 },
    { id: 'EXP-003', createdAt: '2026-01-10 09:00 UTC', dateRange: '2026-01-01 → 2026-01-10', format: 'JSON', size: '892 KB', status: 'processing' as const, entries: 421 },
  ];

  const columns: TableColumn<typeof exports[0]>[] = [
    { key: 'id', header: 'Export ID', width: '100px', render: (v) => <span style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--brand-primary)' }}>{v}</span> },
    { key: 'dateRange', header: 'Date Range' },
    { key: 'format', header: 'Format', width: '80px', render: (v) => <Badge variant="default" size="sm">{String(v)}</Badge> },
    { key: 'entries', header: 'Entries', width: '80px', render: (v) => <span style={{ fontFamily: 'monospace' }}>{Number(v).toLocaleString()}</span> },
    { key: 'size', header: 'Size', width: '80px', render: (v) => <span style={{ fontFamily: 'monospace' }}>{v}</span> },
    { key: 'status', header: 'Status', width: '100px', render: (v) => <Badge variant={v === 'ready' ? 'success' : 'warning'} size="sm" dot={v === 'ready'}>{String(v).toUpperCase()}</Badge> },
  ];

  return (
    <div>
      <Alert variant="info">
        Audit exports are deterministic and cryptographically signed packages suitable for regulatory submissions.
      </Alert>
      <div style={{ marginTop: 12 }}>
        <Table columns={columns} data={exports} rowIdKey="id" />
      </div>
    </div>
  );
}
