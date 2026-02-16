import { useEffect, useRef } from 'react';

const FOCUSABLE = [
  'a[href]',
  'area[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'button:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  'iframe',
  'object',
  'embed',
  '[contenteditable]',
].join(',');

/**
 * Traps focus inside `containerRef` while `active` is true.
 * Restores focus to the previously-focused element on deactivation.
 */
export function useFocusTrap(containerRef: React.RefObject<HTMLElement>, active: boolean) {
  const previousFocus = useRef<Element | null>(null);

  useEffect(() => {
    if (!active) return;

    previousFocus.current = document.activeElement;

    const container = containerRef.current;
    if (!container) return;

    const focusables = () => Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));

    // Move focus into the container
    const first = focusables()[0];
    first?.focus();

    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const items = focusables();
      if (items.length === 0) { e.preventDefault(); return; }

      const first = items[0];
      const last = items[items.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handler);

    return () => {
      document.removeEventListener('keydown', handler);
      (previousFocus.current as HTMLElement)?.focus?.();
    };
  }, [active, containerRef]);
}
