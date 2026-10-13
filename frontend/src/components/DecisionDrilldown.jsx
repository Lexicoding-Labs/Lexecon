import React, { useMemo } from 'react';
import { formatLedgerTime } from '../utils/ledgerTime';

function shorten(value) {
  if (!value || typeof value !== 'string') return 'Not recorded';
  return value.length > 22 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value;
}

function copy(value) {
  if (value != null) navigator.clipboard?.writeText(String(value));
}

function displayRisk(value) {
  if (typeof value === 'number') {
    const label = value >= 4 ? 'Critical' : value >= 3 ? 'High' : value >= 2 ? 'Medium' : 'Low';
    return `${label} (${value})`;
  }
  return value || 'Not recorded';
}

function Field({ label, value, copyValue }) {
  return (
    <div className="stipple-detail-field">
      <dt>{label}</dt>
      <dd>
        <span>{value ?? 'Not recorded'}</span>
        {copyValue != null && <button type="button" className="stipple-detail-copy" onClick={() => copy(copyValue)} aria-label={`Copy ${label}`}>Copy</button>}
      </dd>
    </div>
  );
}

export default function DecisionDrilldown({ entry, verification = 'unchecked' }) {
  const data = entry?.data || {};
  const rawPretty = useMemo(() => JSON.stringify(entry, null, 2), [entry]);
  const outcome = String(data.decision || 'unknown');
  const action = String(data.action || data.proposed_action || 'unknown action');
  const origin = data.evaluation_source === 'synthetic_seed' || data.demo_origin === 'synthetic_seed_no_policy_evaluation'
    ? 'Synthetic seed · no policy evaluation'
    : data.evaluation_source === 'policy_engine'
      ? (data.demo_requested ? 'Policy decision · caller demo flag' : 'Policy decision')
      : data.demo_origin ? 'Legacy demo tag' : 'Origin not recorded';
  const outcomeClass = ['permit', 'allow', 'approved'].includes(outcome) ? 'approved'
    : ['deny', 'denied'].includes(outcome) ? 'denied' : 'pending';
  const checkMessage = verification === 'passed'
    ? 'The source ledger hash chain passed its last integrity check. This does not prove that the action was authorized.'
    : verification === 'failed'
      ? 'The source ledger failed its last integrity check. Inspect the reported failure.'
      : 'Use Verify Integrity to check the source ledger hash chain.';

  return (
    <div className="stipple-detail">
      <div className="stipple-eyebrow">Decision record</div>
      <h2>{action} <span className={`stipple-outcome stipple-outcome--${outcomeClass}`}>{outcome}</span></h2>
      <p className="stipple-detail-lead"><span>{origin}</span>. This view shows the recorded outcome and its evidence; the ledger check is separate.</p>

      <dl className="stipple-detail-summary">
        <div><dt>Actor</dt><dd>{data.actor || data.user_id || 'Not recorded'}</dd></div>
        <div><dt>Risk</dt><dd>{displayRisk(data.risk_level ?? data.riskLevel)}</dd></div>
        <div><dt>Type</dt><dd>{entry?.event_type || 'decision'}</dd></div>
      </dl>

      <section className="stipple-detail-section">
        <h3>Ledger integrity</h3>
        <div className={`stipple-detail-check ${verification === 'failed' ? 'stipple-detail-check--failed' : verification === 'passed' ? '' : 'stipple-detail-check--unchecked'}`}>
          <strong>Ledger check: {verification === 'passed' ? 'passed' : verification === 'failed' ? 'failed' : 'not run'}.</strong>{' '}
          {checkMessage}
        </div>
      </section>

      <section className="stipple-detail-section">
        <h3>Request</h3>
        <dl>
          <Field label="Decision ID" value={data.decision_id || entry?.entry_id} copyValue={data.decision_id || entry?.entry_id} />
          <Field label="Request ID" value={data.request_id} copyValue={data.request_id} />
          <Field label="Timestamp" value={formatLedgerTime(data.timestamp || entry?.timestamp)} copyValue={data.timestamp || entry?.timestamp} />
        </dl>
      </section>

      <details>
        <summary>Policy version and hashes</summary>
        <dl>
          <Field label="Policy version" value={shorten(data.policy_version_hash)} copyValue={data.policy_version_hash} />
          <Field label="Previous hash" value={shorten(entry?.previous_hash)} copyValue={entry?.previous_hash} />
          <Field label="Entry hash" value={shorten(entry?.entry_hash)} copyValue={entry?.entry_hash} />
        </dl>
      </details>
      <details>
        <summary>Raw event JSON</summary>
        <button type="button" className="stipple-button stipple-button-quiet" onClick={() => copy(rawPretty)} style={{ marginTop: 12 }}>Copy JSON</button>
        <pre>{rawPretty}</pre>
      </details>
    </div>
  );
}
