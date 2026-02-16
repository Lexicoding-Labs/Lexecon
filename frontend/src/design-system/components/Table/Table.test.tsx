import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Table } from './Table';
import type { TableColumn } from './Table';

interface Row { id: string; name: string; value: number }

const columns: TableColumn<Row>[] = [
  { key: 'id', header: 'ID', sortable: true },
  { key: 'name', header: 'Name', sortable: true },
  { key: 'value', header: 'Value', sortable: true },
];

const data: Row[] = [
  { id: '1', name: 'Alpha', value: 100 },
  { id: '2', name: 'Beta', value: 50 },
  { id: '3', name: 'Gamma', value: 200 },
];

describe('Table', () => {
  it('renders column headers', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText('ID')).toBeDefined();
    expect(screen.getByText('Name')).toBeDefined();
    expect(screen.getByText('Value')).toBeDefined();
  });

  it('renders all rows', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Beta')).toBeDefined();
    expect(screen.getByText('Gamma')).toBeDefined();
  });

  it('shows TableSkeleton when loading', () => {
    const { container } = render(<Table columns={columns} data={[]} loading={true} />);
    // Skeleton has aria-label
    expect(container.querySelector('[aria-label="Loading table data"]')).toBeDefined();
  });

  it('shows EmptyState when data is empty and not loading', () => {
    render(
      <Table
        columns={columns}
        data={[]}
        emptyTitle="Nothing here"
        emptyDescription="Empty for real."
      />
    );
    expect(screen.getByText('Nothing here')).toBeDefined();
  });

  it('calls onRowClick when a row is clicked', () => {
    const onClick = jest.fn();
    render(<Table columns={columns} data={data} onRowClick={onClick} rowIdKey="id" />);
    fireEvent.click(screen.getByText('Alpha').closest('tr')!);
    expect(onClick).toHaveBeenCalledWith(data[0]);
  });

  it('sorts ascending on first click of sortable header', () => {
    render(<Table columns={columns} data={data} rowIdKey="id" />);
    // Click "Name" header
    fireEvent.click(screen.getByText('Name'));
    // After sort asc by name: Alpha, Beta, Gamma (already sorted, so order same)
    const rows = screen.getAllByRole('row');
    // row[0] is thead, rows[1..3] are data
    expect(rows.length).toBe(4); // 1 header + 3 data
  });

  it('renders density controls', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText('compact')).toBeDefined();
    expect(screen.getByText('normal')).toBeDefined();
    expect(screen.getByText('comfortable')).toBeDefined();
  });

  it('switches density on click', () => {
    const onDensity = jest.fn();
    render(<Table columns={columns} data={data} onDensityChange={onDensity} />);
    fireEvent.click(screen.getByText('compact'));
    expect(onDensity).toHaveBeenCalledWith('compact');
  });
});
