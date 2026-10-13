import React from 'react';
import { render, screen } from '@testing-library/react';
import DecisionDrilldown from './DecisionDrilldown';

const entry = {
  entry_id: 'event-1', event_type: 'decision', timestamp: '2026-10-07T12:00:00Z',
  entry_hash: 'abcdef', previous_hash: '123456',
  data: { decision_id: 'decision-1', decision: 'permit', action: 'read', evaluation_source: 'policy_engine', demo_requested: true },
};

test('detail starts unchecked and labels local example', () => {
  render(<DecisionDrilldown entry={entry} />);
  expect(screen.getByText(/Ledger check: not run/).parentElement.textContent).toContain('Use Verify Integrity');
  expect(screen.getByText('Policy decision · caller demo flag')).not.toBeNull();
});

test('detail reports a failed source ledger check without claiming verification', () => {
  render(<DecisionDrilldown entry={entry} verification="failed" />);
  expect(screen.getByText(/Ledger check: failed/).parentElement.textContent).toContain('Inspect the reported failure');
  expect(screen.queryByText(/Chain verified/)).toBeNull();
});

test('detail labels offset-free ledger time as UTC', () => {
  render(<DecisionDrilldown entry={{ ...entry, timestamp: '2026-10-07T10:29:13' }} />);
  expect(screen.getByText('2026-10-07 10:29:13 UTC')).not.toBeNull();
});
