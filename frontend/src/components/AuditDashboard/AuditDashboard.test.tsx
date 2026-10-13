import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuditDashboard from './AuditDashboard';
import { LedgerAPI, UsageAPI } from '../../api/endpoints';

jest.mock('../../api/endpoints', () => ({
  LedgerAPI: { listEntries: jest.fn(), verify: jest.fn() },
  UsageAPI: { get: jest.fn() },
  EvidenceAPI: { export: jest.fn() },
  AuthAPI: { me: jest.fn() },
  PolicyAPI: { status: jest.fn(), load: jest.fn() },
  DecisionAPI: { decide: jest.fn(), verify: jest.fn() },
}));

test('a failed recheck clears an earlier ledger success and timestamp', async () => {
  (LedgerAPI.listEntries as jest.Mock).mockResolvedValue({ data: { entries: [], total: 0 } });
  (UsageAPI.get as jest.Mock).mockRejectedValue(new Error('usage unavailable'));
  (LedgerAPI.verify as jest.Mock)
    .mockResolvedValueOnce({ data: { valid: true, entries_checked: 1 } })
    .mockRejectedValueOnce({ message: 'Network unavailable' });
  render(<AuditDashboard />);
  await screen.findByRole('button', { name: /Verify Integrity/ });
  fireEvent.click(screen.getByRole('button', { name: /Verify Integrity/ }));
  expect((await screen.findByText(/CHAIN PASSED/)).textContent).toContain('1');
  expect(screen.getByText(/Last verified:/)).not.toBeNull();

  fireEvent.click(screen.getByRole('button', { name: /Verify Integrity/ }));
  await waitFor(() => expect(screen.queryByText(/CHAIN PASSED/)).toBeNull());
  await waitFor(() => expect(document.body.textContent).toContain('Integrity check could not complete:'));
  expect(screen.queryByText(/Last verified:/)).toBeNull();
  expect(document.body.textContent).toContain('Network unavailable');
  expect((LedgerAPI.verify as jest.Mock)).toHaveBeenCalledTimes(2);
});

test('24-hour filter treats offset-free ledger timestamps as UTC and preserves explicit offsets', async () => {
  const now = jest.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-07T10:30:00Z'));
  const entry = (action: string, timestamp: string) => ({
    entry_id: `event-${action}`, event_type: 'decision', timestamp,
    entry_hash: `hash-${action}`, previous_hash: 'previous',
    data: { decision_id: `decision-${action}`, action, decision: 'permit' },
  });
  (LedgerAPI.listEntries as jest.Mock).mockResolvedValue({ data: { entries: [
    entry('outside', '2026-10-06T10:29:59'),
    entry('inside', '2026-10-06T10:30:01'),
    entry('offset-outside', '2026-10-06T06:29:59-04:00'),
    entry('offset-inside', '2026-10-06T06:30:01-04:00'),
  ], total: 4 } });
  (UsageAPI.get as jest.Mock).mockRejectedValue(new Error('usage unavailable'));
  try {
    render(<AuditDashboard />);
    await screen.findByText('inside');
    fireEvent.change(screen.getByRole('combobox', { name: 'Date range' }), { target: { value: '24hours' } });
    expect(screen.queryByText('outside')).toBeNull();
    expect(screen.queryByText('offset-outside')).toBeNull();
    expect(screen.getByText('inside')).not.toBeNull();
    expect(screen.getByText('offset-inside')).not.toBeNull();
    expect(screen.getAllByText('2026-10-06 10:30:01 UTC')).toHaveLength(2);
  } finally {
    now.mockRestore();
  }
});
