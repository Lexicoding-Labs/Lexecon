import React, { useState, useRef, useEffect, useCallback } from 'react';
import { TableSkeleton } from '../Skeleton/Skeleton';
import { EmptyState } from '../EmptyState/EmptyState';

// ─── Types ────────────────────────────────────────────────

export type SortDirection = 'asc' | 'desc' | null;
export type Density = 'compact' | 'normal' | 'comfortable';

export interface TableColumn<T = Record<string, unknown>> {
  key: string;
  header: string;
  sortable?: boolean;
  width?: string;
  render?: (value: unknown, row: T) => React.ReactNode;
  align?: 'left' | 'right' | 'center';
}

export interface TableProps<T extends Record<string, unknown> = Record<string, unknown>> {
  columns: TableColumn<T>[];
  data: T[];
  loading?: boolean;
  emptyIcon?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyActions?: { label: string; onClick: () => void }[];
  onRowClick?: (row: T) => void;
  rowIdKey?: string;
  /** Initial sort column */
  defaultSortKey?: string;
  defaultSortDir?: SortDirection;
  /** Controlled density */
  density?: Density;
  onDensityChange?: (d: Density) => void;
  className?: string;
}

// ─── Helpers ──────────────────────────────────────────────

const densityPadding: Record<Density, { y: number; x: number }> = {
  compact: { y: 8, x: 12 },
  normal: { y: 14, x: 16 },
  comfortable: { y: 20, x: 24 },
};

function sortData<T extends Record<string, unknown>>(data: T[], key: string | null, dir: SortDirection): T[] {
  if (!key || !dir) return data;
  return [...data].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
    return dir === 'asc' ? cmp : -cmp;
  });
}

// ─── Component ────────────────────────────────────────────

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  loading = false,
  emptyIcon = '📭',
  emptyTitle = 'No data found',
  emptyDescription,
  emptyActions = [],
  onRowClick,
  rowIdKey,
  defaultSortKey,
  defaultSortDir = 'desc',
  density: controlledDensity,
  onDensityChange,
  className = '',
}: TableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(defaultSortKey || null);
  const [sortDir, setSortDir] = useState<SortDirection>(defaultSortKey ? defaultSortDir : null);
  const [density, setDensityLocal] = useState<Density>(controlledDensity || 'normal');
  const [stickyActive, setStickyActive] = useState(false);
  const [hoveredRowId, setHoveredRowId] = useState<string | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  const activeDensity = controlledDensity || density;
  const pad = densityPadding[activeDensity];

  // Density change handler
  const handleDensityChange = useCallback((d: Density) => {
    setDensityLocal(d);
    onDensityChange?.(d);
  }, [onDensityChange]);

  // Scroll handler for sticky shadow
  useEffect(() => {
    const wrapper = tableRef.current;
    if (!wrapper) return;
    const onScroll = () => {
      setStickyActive(wrapper.scrollTop > 0);
    };
    wrapper.addEventListener('scroll', onScroll, { passive: true });
    return () => wrapper.removeEventListener('scroll', onScroll);
  }, []);

  // Sort handler
  const handleSort = useCallback((col: TableColumn<T>) => {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      if (sortDir === 'asc') setSortDir('desc');
      else if (sortDir === 'desc') { setSortKey(null); setSortDir(null); }
    } else {
      setSortKey(col.key);
      setSortDir('asc');
    }
  }, [sortKey, sortDir]);

  // Keyboard nav: arrow keys on tbody
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTableSectionElement>, rowIndex: number) => {
    const rows = tableRef.current?.querySelectorAll('tbody tr');
    if (!rows) return;
    let target: Element | null = null;
    if (e.key === 'ArrowDown') { e.preventDefault(); target = rows[rowIndex + 1] as Element; }
    if (e.key === 'ArrowUp') { e.preventDefault(); target = rows[rowIndex - 1] as Element; }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); (e.currentTarget as HTMLElement).click(); }
    if (target) (target as HTMLElement).focus();
  }, []);

  const sorted = sortData(data, sortKey, sortDir);

  // ── Render ──
  if (loading) {
    return (
      <div className={className} style={{ borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden', background: 'var(--bg-elevated)' }}>
        <TableSkeleton rows={5} columns={columns.length} />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className={className} style={{ borderRadius: 12, border: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} actions={emptyActions} />
      </div>
    );
  }

  const sortIcon = (col: TableColumn<T>) => {
    if (!col.sortable) return null;
    if (sortKey !== col.key) return <span style={{ opacity: 0.3, marginLeft: 4 }}>↕</span>;
    return <span style={{ marginLeft: 4 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className={className} style={{ borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden', background: 'var(--bg-elevated)' }}>
      {/* Density controls */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: 4,
        padding: '8px 12px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
      }}>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 6, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Density</span>
        {(['compact', 'normal', 'comfortable'] as Density[]).map((d) => (
          <button
            key={d}
            onClick={() => handleDensityChange(d)}
            aria-pressed={activeDensity === d}
            style={{
              padding: '3px 10px',
              borderRadius: 6,
              border: 'none',
              background: activeDensity === d ? 'var(--brand-primary)' : 'transparent',
              color: activeDensity === d ? '#fff' : 'var(--text-secondary)',
              fontSize: 11,
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 150ms cubic-bezier(0.4,0,0.2,1)',
              textTransform: 'capitalize',
            }}
          >
            {d}
          </button>
        ))}
      </div>

      {/* Scrollable table */}
      <div ref={tableRef} style={{ overflowY: 'auto', maxHeight: 600 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead style={{
            position: 'sticky',
            top: 0,
            zIndex: 2,
            background: 'var(--bg-secondary)',
            boxShadow: stickyActive ? 'var(--shadow-sticky)' : 'none',
            transition: 'box-shadow 200ms cubic-bezier(0.4,0,0.2,1)',
          }}>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col)}
                  style={{
                    padding: `${pad.y}px ${pad.x}px`,
                    textAlign: col.align || 'left',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: sortKey === col.key ? 'var(--brand-primary)' : 'var(--text-secondary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    borderBottom: '1px solid var(--border)',
                    width: col.width,
                    whiteSpace: 'nowrap' as const,
                    cursor: col.sortable ? 'pointer' : 'default',
                    userSelect: 'none',
                    transition: 'color 150ms cubic-bezier(0.4,0,0.2,1)',
                  }}
                  aria-sort={sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  role="columnheader"
                >
                  {col.header}
                  {sortIcon(col)}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {sorted.map((row, rowIndex) => {
              const id = rowIdKey ? String(row[rowIdKey]) : String(rowIndex);
              const isHovered = hoveredRowId === id;

              return (
                <tr
                  key={id}
                  tabIndex={onRowClick ? 0 : -1}
                  role={onRowClick ? 'row' : undefined}
                  aria-label={onRowClick ? `Row ${rowIndex + 1}, click to view details` : undefined}
                  onClick={() => onRowClick?.(row)}
                  onKeyDown={(e) => handleKeyDown(e, rowIndex)}
                  onMouseEnter={() => setHoveredRowId(id)}
                  onMouseLeave={() => setHoveredRowId(null)}
                  style={{
                    cursor: onRowClick ? 'pointer' : 'default',
                    background: isHovered ? 'var(--brand-primary-subtle)' : 'transparent',
                    transition: 'background 150ms cubic-bezier(0.4,0,0.2,1)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        padding: `${pad.y}px ${pad.x}px`,
                        fontSize: '0.875rem',
                        color: 'var(--text-primary)',
                        textAlign: col.align || 'left',
                        position: 'relative',
                      }}
                    >
                      {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                    </td>
                  ))}

                  {/* Inline row actions – fade in on hover */}
                  {onRowClick && isHovered && (
                    <td style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', zIndex: 1 }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); onRowClick(row); }}
                        style={{
                          padding: '4px 12px',
                          borderRadius: 6,
                          border: '1px solid var(--border)',
                          background: 'var(--bg-elevated)',
                          color: 'var(--brand-primary)',
                          fontSize: '0.8125rem',
                          fontWeight: 500,
                          cursor: 'pointer',
                          boxShadow: 'var(--shadow-sm)',
                          animation: 'fadeIn 150ms cubic-bezier(0.4,0,0.2,1)',
                        }}
                      >
                        View →
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Table;
