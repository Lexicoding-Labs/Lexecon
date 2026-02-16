import React from 'react';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
}

const shimmerBase: React.CSSProperties = {
  background: 'linear-gradient(90deg, var(--bg-tertiary) 25%, var(--border) 37%, var(--bg-tertiary) 63%) 200% 0 / 400% 100%',
  animation: 'shimmer 1.4s ease-in-out infinite',
};

export function Skeleton({ width = '100%', height = 16, borderRadius = 4, className = '' }: SkeletonProps) {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        borderRadius,
        ...shimmerBase,
      }}
      aria-hidden="true"
    />
  );
}

// Pre-built skeleton layouts that mirror real component shapes

export function TableSkeleton({ rows = 5, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div aria-label="Loading table data" aria-busy="true">
      {/* Header row */}
      <div style={{ display: 'flex', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} height={14} width={`${60 + (i % 3) * 30}px`} />
        ))}
      </div>
      {/* Body rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: 12, padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          {Array.from({ length: columns }).map((_, c) => (
            <Skeleton key={c} height={14} width={`${40 + ((r + c) % 4) * 25}px`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${count}, 1fr)`, gap: 24 }} aria-label="Loading cards" aria-busy="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ padding: 24, borderRadius: 12, border: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
          <Skeleton height={12} width="60%" />
          <Skeleton height={28} width="80%" style={{ marginTop: 12 }} borderRadius={6} />
          <Skeleton height={12} width="45%" style={{ marginTop: 10 }} />
        </div>
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div aria-label="Loading page" aria-busy="true">
      {/* Header */}
      <div style={{ padding: '24px 32px', borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <Skeleton height={24} width="240px" />
        <Skeleton height={14} width="380px" style={{ marginTop: 8 }} />
      </div>
      {/* Stats row */}
      <div style={{ padding: '24px 32px' }}>
        <CardSkeleton count={4} />
      </div>
      {/* Table */}
      <div style={{ padding: '0 32px 32px' }}>
        <TableSkeleton rows={6} columns={7} />
      </div>
    </div>
  );
}

// Helper: attach style prop forwarding to base Skeleton
Skeleton.defaultProps = {};

export default Skeleton;
