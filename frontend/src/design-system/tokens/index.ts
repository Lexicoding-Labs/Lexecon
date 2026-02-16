/**
 * Lexecon Design Tokens – TypeScript
 *
 * Single source of truth. Re-exports all token modules.
 * The legacy `lexecon-design-tokens.js` is kept for backward compatibility
 * but new code should import from here.
 */

import * as colors from './colors';
import * as typography from './typography';
import * as animations from './animations';

export { colors, typography, animations };

// Convenience re-exports used throughout the codebase
export const { brand, neutral, semantic, governance, dataViz, darkSurface } = colors;
export const { fontFamily, fontSize, fontWeight } = typography;
export const { duration, easing, transition } = animations;

// Spacing (4px grid)
export const spacing = {
  0: '0',
  px: '0.0625rem',
  1: '0.25rem',
  2: '0.5rem',
  3: '0.75rem',
  4: '1rem',
  5: '1.25rem',
  6: '1.5rem',
  8: '2rem',
  10: '2.5rem',
  12: '3rem',
  16: '4rem',
  20: '5rem',
  24: '6rem',
} as const;

export const border = {
  radius: {
    sm: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    full: '9999px',
  },
  width: { 1: '1px', 2: '2px', 4: '4px' },
} as const;

export const shadows = {
  sm: '0 1px 2px 0 rgba(0,0,0,0.05)',
  base: '0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1)',
  md: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)',
  lg: '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)',
  xl: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
  focusRing: '0 0 0 3px rgba(99,102,241,0.5)',
} as const;

export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  backdrop: 1040,
  modal: 1050,
  max: 9999,
} as const;

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;
