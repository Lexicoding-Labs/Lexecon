import React from 'react';

export type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info';
export type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  pulseDot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; dotColor: string }> = {
  default: { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)', dotColor: 'var(--text-tertiary)' },
  primary: { bg: 'var(--brand-primary-subtle)', text: 'var(--brand-text)', dotColor: 'var(--brand-primary)' },
  success: { bg: 'var(--success-subtle)', text: 'var(--success-text)', dotColor: 'var(--success)' },
  warning: { bg: 'var(--warning-subtle)', text: 'var(--warning-text)', dotColor: 'var(--warning)' },
  error: { bg: 'var(--error-subtle)', text: 'var(--error-text)', dotColor: 'var(--error)' },
  info: { bg: 'var(--info-subtle)', text: 'var(--info-text)', dotColor: 'var(--info)' },
};

const sizeStyles: Record<BadgeSize, { padding: string; fontSize: string; dotSize: number }> = {
  sm: { padding: '2px 8px', fontSize: '11px', dotSize: 6 },
  md: { padding: '3px 10px', fontSize: '12px', dotSize: 7 },
  lg: { padding: '4px 12px', fontSize: '13px', dotSize: 8 },
};

export function Badge({ children, variant = 'default', size = 'md', dot = false, pulseDot = false, className = '' }: BadgeProps) {
  const v = variantStyles[variant];
  const s = sizeStyles[size];

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: dot || pulseDot ? 6 : 0,
        padding: s.padding,
        fontSize: s.fontSize,
        fontWeight: 600,
        lineHeight: 1,
        borderRadius: 9999,
        backgroundColor: v.bg,
        color: v.text,
        whiteSpace: 'nowrap' as const,
      }}
    >
      {(dot || pulseDot) && (
        <span
          style={{
            display: 'inline-block',
            width: s.dotSize,
            height: s.dotSize,
            borderRadius: '50%',
            backgroundColor: v.dotColor,
            animation: pulseDot ? 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite' : undefined,
          }}
        />
      )}
      {children}
    </span>
  );
}

export default Badge;
