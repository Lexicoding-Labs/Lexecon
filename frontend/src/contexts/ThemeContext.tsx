import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ThemeMode } from '../types/theme.types';

interface ThemeContextValue {
  mode: ThemeMode;
  resolved: 'light' | 'dark';
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'system',
  resolved: 'light',
  setMode: () => {},
});

function resolveMode(mode: ThemeMode): 'light' | 'dark' {
  if (mode !== 'system') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    try {
      return (localStorage.getItem('lexecon_theme') as ThemeMode) || 'system';
    } catch {
      return 'system';
    }
  });

  const resolved = resolveMode(mode);

  // Apply class to <html> root
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', resolved === 'dark');
  }, [resolved]);

  // Listen for system preference changes when mode === 'system'
  useEffect(() => {
    if (mode !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      document.documentElement.classList.toggle('dark', mq.matches);
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      localStorage.setItem('lexecon_theme', next);
    } catch { /* ignore */ }
  }, []);

  return (
    <ThemeContext.Provider value={{ mode, resolved, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

// Standalone toggle button – drop into any layout
export function ThemeToggle({ className = '' }: { className?: string }) {
  const { mode, resolved, setMode } = useTheme();

  const cycle = useCallback(() => {
    if (mode === 'light') setMode('dark');
    else if (mode === 'dark') setMode('system');
    else setMode('light');
  }, [mode, setMode]);

  const icon = resolved === 'dark' ? '☀️' : '🌙';
  const label = mode === 'system' ? 'System' : mode === 'light' ? 'Light' : 'Dark';

  return (
    <button
      onClick={cycle}
      aria-label={`Theme: ${label}. Click to cycle.`}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 10px',
        borderRadius: 6,
        border: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
        color: 'var(--text-primary)',
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: 500,
        transition: 'all 200ms cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}
