import React from 'react';
import { render, screen } from '@testing-library/react';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText('Active')).toBeDefined();
  });

  it('renders a dot when dot=true', () => {
    const { container } = render(<Badge dot>With Dot</Badge>);
    // The dot is an inline-block span before the text
    const spans = container.querySelectorAll('span');
    expect(spans.length).toBeGreaterThanOrEqual(2); // wrapper + dot
  });

  it('renders a pulsing dot when pulseDot=true', () => {
    const { container } = render(<Badge pulseDot variant="success">Live</Badge>);
    const dotEl = container.querySelector('[style*="animation"]');
    expect(dotEl).toBeDefined();
  });

  it('applies variant styles without crashing', () => {
    const variants = ['default', 'primary', 'success', 'warning', 'error', 'info'] as const;
    variants.forEach((v) => {
      const { unmount } = render(<Badge variant={v}>{v}</Badge>);
      expect(screen.getByText(v)).toBeDefined();
      unmount();
    });
  });

  it('applies size styles without crashing', () => {
    const sizes = ['sm', 'md', 'lg'] as const;
    sizes.forEach((s) => {
      const { unmount } = render(<Badge size={s}>Size</Badge>);
      expect(screen.getByText('Size')).toBeDefined();
      unmount();
    });
  });
});
