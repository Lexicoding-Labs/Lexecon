import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import GuidedExample from './GuidedExample';
import { AuthAPI, DecisionAPI, PolicyAPI } from '../api/endpoints';

jest.mock('../api/endpoints', () => ({
  AuthAPI: { me: jest.fn() },
  DecisionAPI: { decide: jest.fn(), verify: jest.fn() },
  PolicyAPI: { status: jest.fn(), load: jest.fn() },
}));

const me = AuthAPI.me as jest.Mock;
const status = PolicyAPI.status as jest.Mock;
const load = PolicyAPI.load as jest.Mock;
const decide = DecisionAPI.decide as jest.Mock;
const verify = DecisionAPI.verify as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
  me.mockResolvedValue({ data: { user: { username: 'admin', role: 'admin' } } });
  status.mockResolvedValue({ data: { terms_count: 0, relations_count: 0 } });
  load.mockResolvedValue({ data: { status: 'success' } });
  decide.mockImplementation(({ proposed_action }) => Promise.resolve({ data: {
    decision: proposed_action === 'read' ? 'permit' : 'deny', ledger_entry_hash: proposed_action,
  } }));
  verify.mockResolvedValue({ data: { verified: true } });
});

test('loads a policy and verifies both real API decision responses', async () => {
  const onComplete = jest.fn().mockResolvedValue(undefined);
  render(<GuidedExample onComplete={onComplete} />);
  fireEvent.click(screen.getByRole('button', { name: 'Run policy example' }));
  expect((await screen.findByRole('status')).textContent).toContain('permit');
  expect(screen.getByRole('status').textContent).toContain('deny');
  expect(screen.getByRole('status').textContent).toContain('passed');
  expect(load).toHaveBeenCalledTimes(1);
  expect(decide).toHaveBeenCalledTimes(2);
  expect(verify).toHaveBeenCalledTimes(2);
  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
});

test('does not replace an existing policy when the user declines', async () => {
  status.mockResolvedValue({ data: { terms_count: 0, relations_count: 2 } });
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(false);
  try {
    render(<GuidedExample onComplete={jest.fn().mockResolvedValue(undefined)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Run policy example' }));
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    expect(load).not.toHaveBeenCalled();
    expect(decide).not.toHaveBeenCalled();
  } finally {
    confirm.mockRestore();
  }
});
