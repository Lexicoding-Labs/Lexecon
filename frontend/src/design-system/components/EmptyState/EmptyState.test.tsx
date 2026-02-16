import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="Nothing found" />);
    expect(screen.getByText('Nothing found')).toBeDefined();
  });

  it('renders description when provided', () => {
    render(<EmptyState title="Empty" description="Try again later." />);
    expect(screen.getByText('Try again later.')).toBeDefined();
  });

  it('renders icon when provided', () => {
    const { container } = render(<EmptyState icon="📭" title="Empty" />);
    expect(container.textContent?.includes('📭')).toBe(true);
  });

  it('renders action buttons and fires onClick', () => {
    const handler = jest.fn();
    render(
      <EmptyState
        title="Empty"
        actions={[{ label: 'Load Data', onClick: handler }]}
      />
    );
    fireEvent.click(screen.getByText('Load Data'));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('renders multiple action buttons', () => {
    render(
      <EmptyState
        title="Empty"
        actions={[
          { label: 'Primary Action', onClick: () => {} },
          { label: 'Secondary Action', onClick: () => {}, variant: 'secondary' },
        ]}
      />
    );
    expect(screen.getByText('Primary Action')).toBeDefined();
    expect(screen.getByText('Secondary Action')).toBeDefined();
  });
});
