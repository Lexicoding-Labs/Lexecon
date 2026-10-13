import React from 'react';

interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

interface EmptyStateProps {
  icon?: string | React.ReactNode;
  title: string;
  description?: string;
  actions?: EmptyStateAction[];
  className?: string;
}

export function EmptyState({ icon, title, description, actions = [], className = '' }: EmptyStateProps) {
  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '56px 24px',
        animation: 'fadeIn 300ms cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {icon && (
        <div style={{ fontSize: 40, marginBottom: 16, opacity: 0.6 }}>
          {icon}
        </div>
      )}

      <h3 style={{
        fontSize: '1.125rem',
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: description ? 8 : 0,
      }}>
        {title}
      </h3>

      {description && (
        <p style={{
          fontSize: '0.875rem',
          color: 'var(--text-secondary)',
          maxWidth: 400,
          lineHeight: 1.5,
        }}>
          {description}
        </p>
      )}

      {actions.length > 0 && (
        <div style={{ display: 'flex', gap: 10, marginTop: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
          {actions.map((action, i) => (
            <button
              key={i}
              onClick={action.onClick}
              style={{
                padding: '8px 18px',
                borderRadius: 8,
                border: action.variant === 'secondary' ? '1px solid var(--border)' : 'none',
                background: action.variant === 'secondary' ? 'var(--bg-tertiary)' : 'var(--brand-primary)',
                color: action.variant === 'secondary' ? 'var(--text-primary)' : '#fff',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default EmptyState;
