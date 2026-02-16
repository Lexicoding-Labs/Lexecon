export const duration = {
  instant: '0ms',
  fast: '150ms',
  normal: '200ms',
  slow: '300ms',
  slower: '500ms',
} as const;

export const easing = {
  smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
  bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
} as const;

export const transition = {
  all: `all ${duration.normal} ${easing.smooth}`,
  colors: `color ${duration.normal} ${easing.smooth}, background-color ${duration.normal} ${easing.smooth}, border-color ${duration.normal} ${easing.smooth}`,
  transform: `transform ${duration.normal} ${easing.smooth}`,
  shadow: `box-shadow ${duration.normal} ${easing.smooth}`,
  opacity: `opacity ${duration.normal} ${easing.smooth}`,
} as const;

// Button hover: lift 1px
export const buttonLift = {
  hover: { transform: 'translateY(-1px)', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' },
  active: { transform: 'translateY(0px)', boxShadow: '0 1px 2px 0 rgba(0,0,0,0.05)' },
} as const;

// Card hover elevation
export const cardElevation = {
  default: '0 1px 3px 0 rgba(0,0,0,0.1)',
  hover: '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)',
} as const;
