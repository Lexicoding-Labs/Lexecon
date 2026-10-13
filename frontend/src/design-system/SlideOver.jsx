import React, { useEffect, useRef } from 'react';

export default function SlideOver({ open, title, onClose, children }) {
  const panelRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose?.();
      }
      if (event.key !== 'Tab') return;
      const focusables = [...(panelRef.current?.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])') || [])]
        .filter((node) => !node.disabled && node.getClientRects().length > 0);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="stipple-modal" role="dialog" aria-modal="true" aria-labelledby="stipple-detail-title">
      <div className="stipple-scrim" onClick={onClose} aria-hidden="true" />
      <div className="stipple-detail-panel" ref={panelRef}>
        <div className="stipple-detail-panel-header">
          <div id="stipple-detail-title">{title || 'Decision details'}</div>
          <button type="button" ref={closeRef} onClick={onClose} aria-label="Close" className="stipple-button stipple-button-quiet">Close</button>
        </div>
        <div className="stipple-detail-panel-content">{children}</div>
      </div>
    </div>
  );
}
