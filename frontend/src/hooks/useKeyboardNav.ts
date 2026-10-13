import { useCallback } from 'react';

/**
 * Returns a keyDown handler that enables ArrowUp/ArrowDown navigation
 * among sibling elements matched by `selector` inside `container`.
 *
 * Usage:
 *   const handleKey = useKeyboardNav(containerRef, 'tr[tabindex]');
 *   <tr tabIndex={0} onKeyDown={handleKey} …>
 */
export function useKeyboardNav(
  containerRef: React.RefObject<HTMLElement>,
  selector: string,
) {
  return useCallback((e: React.KeyboardEvent) => {
    const container = containerRef.current;
    if (!container) return;

    const items = Array.from(container.querySelectorAll<HTMLElement>(selector));
    const index = items.indexOf(e.currentTarget as HTMLElement);
    if (index === -1) return;

    let next: HTMLElement | null = null;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        next = items[index + 1] ?? null;
        break;
      case 'ArrowUp':
        e.preventDefault();
        next = items[index - 1] ?? null;
        break;
      case 'Home':
        e.preventDefault();
        next = items[0] ?? null;
        break;
      case 'End':
        e.preventDefault();
        next = items[items.length - 1] ?? null;
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        (e.currentTarget as HTMLElement).click();
        return;
    }

    next?.focus();
  }, [containerRef, selector]);
}
