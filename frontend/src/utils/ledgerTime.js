// Historical ledger entries store UTC wall-clock values without an offset.
// Interpret them as UTC for display and filtering; never rewrite the signed event.
export function parseLedgerTime(value) {
  if (!value) return NaN;
  const raw = String(value).trim();
  const utcWithoutOffset = /^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
  const normalized = utcWithoutOffset.test(raw)
    ? `${raw.replace(/[Tt ]/, 'T')}Z`
    : raw;
  return Date.parse(normalized);
}

export function formatLedgerTime(value) {
  if (!value) return 'Unknown';
  const milliseconds = parseLedgerTime(value);
  return Number.isNaN(milliseconds)
    ? String(value)
    : `${new Date(milliseconds).toISOString().replace('T', ' ').slice(0, 19)} UTC`;
}
