import type { Meta, StoryObj } from '@storybook/react';
import { Table } from './Table';
import type { TableColumn } from './Table';
import { Badge } from '../Badge/Badge';

const meta: Meta<typeof Table> = {
  component: Table,
  title: 'Design System / Table',
};
export default meta;
type Story = StoryObj<typeof Table>;

// ─── Sample data ──────────────────────────────────────────

interface SampleRow {
  id: string;
  name: string;
  status: string;
  risk: string;
  value: string;
}

const sampleData: SampleRow[] = [
  { id: 'DEC-001', name: 'Model inference request', status: 'approved', risk: 'low', value: '$12.40' },
  { id: 'DEC-002', name: 'Data access escalation', status: 'escalated', risk: 'high', value: '$89.00' },
  { id: 'DEC-003', name: 'PII export denied', status: 'denied', risk: 'critical', value: '$0.00' },
  { id: 'DEC-004', name: 'Batch processing approved', status: 'approved', risk: 'medium', value: '$34.20' },
  { id: 'DEC-005', name: 'Override by compliance', status: 'override', risk: 'medium', value: '$45.10' },
];

const statusVariant: Record<string, any> = {
  approved: 'success', denied: 'error', escalated: 'warning', override: 'primary',
};
const riskVariant: Record<string, any> = {
  low: 'success', medium: 'warning', high: 'warning', critical: 'error',
};

const columns: TableColumn<SampleRow>[] = [
  { key: 'id', header: 'ID', sortable: true, width: '100px', render: (v) => <span style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--brand-primary)' }}>{v}</span> },
  { key: 'name', header: 'Action', sortable: true },
  { key: 'risk', header: 'Risk', sortable: true, width: '90px', render: (v) => <Badge variant={riskVariant[v as string]}>{String(v).toUpperCase()}</Badge> },
  { key: 'status', header: 'Status', sortable: true, width: '110px', render: (v) => <Badge variant={statusVariant[v as string]} pulseDot>{String(v).toUpperCase()}</Badge> },
  { key: 'value', header: 'Value', sortable: true, width: '90px', align: 'right' },
];

// ─── Stories ──────────────────────────────────────────────

export const Default: Story = {
  args: {
    columns,
    data: sampleData,
    rowIdKey: 'id',
    defaultSortKey: 'id',
    onRowClick: (row) => console.log('Row clicked:', row),
  },
};

export const LoadingState: Story = {
  name: 'Loading Skeleton',
  args: {
    columns,
    data: [],
    loading: true,
  },
};

export const EmptyState: Story = {
  name: 'Empty State',
  args: {
    columns,
    data: [],
    emptyIcon: '📭',
    emptyTitle: 'No decisions yet',
    emptyDescription: 'Try loading some demo data to populate the ledger.',
    emptyActions: [{ label: 'Load Demo', onClick: () => console.log('load demo') }],
  },
};

export const Compact: Story = {
  name: 'Compact Density',
  args: {
    columns,
    data: sampleData,
    rowIdKey: 'id',
    density: 'compact',
  },
};

export const Comfortable: Story = {
  name: 'Comfortable Density',
  args: {
    columns,
    data: sampleData,
    rowIdKey: 'id',
    density: 'comfortable',
  },
};
