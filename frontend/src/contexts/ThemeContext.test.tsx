import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, useTheme, ThemeToggle } from './ThemeContext';

function TestConsumer() {
  const { mode, resolved } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="resolved">{resolved}</span>
    </div>
  );
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.removeItem('lexecon_theme');
    document.documentElement.classList.remove('dark');
  });

  it('provides default system mode', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('mode').textContent).toBe('system');
  });

  it('reads persisted mode from localStorage', () => {
    localStorage.setItem('lexecon_theme', 'dark');
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('mode').textContent).toBe('dark');
    expect(screen.getByTestId('resolved').textContent).toBe('dark');
  });

  it('persists mode to localStorage on change', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
        <ThemeToggle />
      </ThemeProvider>
    );
    // Initial: system. Click once → light
    const btn = screen.getByRole('button', { name: /theme/i });
    fireEvent.click(btn);
    expect(localStorage.getItem('lexecon_theme')).toBe('light');
  });
});

describe('ThemeToggle', () => {
  it('renders with accessible label', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );
    const btn = screen.getByRole('button', { name: /theme/i });
    expect(btn).toBeDefined();
  });

  it('cycles through light → dark → system', () => {
    localStorage.setItem('lexecon_theme', 'light');
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );
    const btn = screen.getByRole('button', { name: /theme/i });
    // light → dark
    fireEvent.click(btn);
    expect(localStorage.getItem('lexecon_theme')).toBe('dark');
    // dark → system
    fireEvent.click(btn);
    expect(localStorage.getItem('lexecon_theme')).toBe('system');
    // system → light
    fireEvent.click(btn);
    expect(localStorage.getItem('lexecon_theme')).toBe('light');
  });
});
