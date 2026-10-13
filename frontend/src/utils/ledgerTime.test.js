import { formatLedgerTime, parseLedgerTime } from './ledgerTime';

test('offset-free historical ledger time is UTC', () => {
  expect(parseLedgerTime('2026-10-07T10:29:13.123456')).toBe(Date.parse('2026-10-07T10:29:13.123456Z'));
  expect(formatLedgerTime('2026-10-07T10:29:13')).toBe('2026-10-07 10:29:13 UTC');
});

test('explicit offsets retain their actual instant', () => {
  expect(formatLedgerTime('2026-10-07T06:29:13-04:00')).toBe('2026-10-07 10:29:13 UTC');
  expect(parseLedgerTime('2026-10-07T12:29:13+02:00')).toBe(parseLedgerTime('2026-10-07T10:29:13Z'));
});
