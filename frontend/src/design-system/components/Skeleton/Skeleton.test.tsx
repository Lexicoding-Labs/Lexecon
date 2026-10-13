import React from 'react';
import { render } from '@testing-library/react';
import { Skeleton, TableSkeleton, CardSkeleton, PageSkeleton } from './Skeleton';

describe('Skeleton', () => {
  it('renders a single skeleton element', () => {
    const { container } = render(<Skeleton width="100px" height={20} />);
    const el = container.firstElementChild;
    expect(el).toBeDefined();
    expect(el?.getAttribute('aria-hidden')).toBe('true');
  });
});

describe('TableSkeleton', () => {
  it('renders with default row/column count', () => {
    const { container } = render(<TableSkeleton />);
    expect(container.querySelector('[aria-label="Loading table data"]')).toBeDefined();
  });

  it('renders custom rows and columns', () => {
    const { container } = render(<TableSkeleton rows={3} columns={4} />);
    expect(container.querySelector('[aria-busy="true"]')).toBeDefined();
  });
});

describe('CardSkeleton', () => {
  it('renders 4 card placeholders by default', () => {
    const { container } = render(<CardSkeleton />);
    const grid = container.firstElementChild as HTMLElement;
    expect(grid?.children.length).toBe(4);
  });
});

describe('PageSkeleton', () => {
  it('renders without error', () => {
    const { container } = render(<PageSkeleton />);
    expect(container.querySelector('[aria-label="Loading page"]')).toBeDefined();
  });
});
