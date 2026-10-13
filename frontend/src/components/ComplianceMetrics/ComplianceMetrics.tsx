import React from 'react';

interface MetricItem {
  label: string;
  value: number;
  total: number;
  color: string;
}

interface ComplianceMetricsProps {
  metrics?: MetricItem[];
}

const defaultMetrics: MetricItem[] = [
  { label: 'Data Access Control', value: 847, total: 1000, color: 'var(--brand-primary)' },
  { label: 'Model Risk Assessment', value: 623, total: 1000, color: 'var(--success)' },
  { label: 'PII Protection', value: 512, total: 1000, color: 'var(--warning)' },
  { label: 'Escalation Threshold', value: 398, total: 1000, color: 'var(--info)' },
  { label: 'Override Authorization', value: 467, total: 1000, color: 'var(--error)' },
];

export function ComplianceMetrics({ metrics = defaultMetrics }: ComplianceMetricsProps) {
  return (
    <div style={{
      borderRadius: 12,
      border: '1px solid var(--border)',
      background: 'var(--bg-elevated)',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
      }}>
        <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
          Sample Policy Metrics
        </h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
          Illustrative values; not calculated from your ledger
        </p>
      </div>

      <div style={{ padding: 20 }}>
        {metrics.map((m, i) => {
          const pct = Math.min((m.value / m.total) * 100, 100);
          return (
            <div key={i} style={{ marginBottom: i < metrics.length - 1 ? 16 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-primary)' }}>{m.label}</span>
                <span style={{ fontSize: '0.8125rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                  {m.value.toLocaleString()} ({pct.toFixed(1)}%)
                </span>
              </div>
              <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${pct}%`,
                  background: m.color,
                  borderRadius: 3,
                  transition: 'width 600ms cubic-bezier(0.4,0,0.2,1)',
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ComplianceMetrics;
