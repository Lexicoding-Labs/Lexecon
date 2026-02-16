// Unified color system – indigo #6366F1 primary
// Dark mode palette layered via CSS custom properties in global.css

export const brand = {
  primary: {
    50: '#EEF2FF',
    100: '#E0E7FF',
    200: '#C7D2FE',
    300: '#A5B4FC',
    400: '#818CF8',
    500: '#6366F1',
    600: '#4F46E5',
    700: '#4338CA',
    800: '#3730A3',
    900: '#312E81',
    950: '#1E1B4B',
  },
  secondary: {
    50: '#F0FDFA',
    100: '#CCFBF1',
    200: '#99F6E4',
    300: '#5EEAD4',
    400: '#2DD4BF',
    500: '#14B8A6',
    600: '#0D9488',
    700: '#0F766E',
    800: '#115E59',
    900: '#134E4A',
    950: '#042F2E',
  },
} as const;

export const neutral = {
  0: '#FFFFFF',
  50: '#FAFAFA',
  100: '#F5F5F5',
  200: '#E5E5E5',
  300: '#D4D4D4',
  400: '#A3A3A3',
  500: '#737373',
  600: '#525252',
  700: '#404040',
  800: '#262626',
  900: '#171717',
  950: '#0A0A0A',
} as const;

export const semantic = {
  success: {
    50: '#F0FDF4', 100: '#DCFCE7', 200: '#BBF7D0', 300: '#86EFAC',
    400: '#4ADE80', 500: '#22C55E', 600: '#16A34A', 700: '#15803D',
    800: '#166534', 900: '#14532D',
  },
  warning: {
    50: '#FFFBEB', 100: '#FEF3C7', 200: '#FDE68A', 300: '#FCD34D',
    400: '#FBBF24', 500: '#F59E0B', 600: '#D97706', 700: '#B45309',
    800: '#92400E', 900: '#78350F',
  },
  error: {
    50: '#FEF2F2', 100: '#FEE2E2', 200: '#FECACA', 300: '#FCA5A5',
    400: '#F87171', 500: '#EF4444', 600: '#DC2626', 700: '#B91C1C',
    800: '#991B1B', 900: '#7F1D1D',
  },
  info: {
    50: '#EFF6FF', 100: '#DBEAFE', 200: '#BFDBFE', 300: '#93C5FD',
    400: '#60A5FA', 500: '#3B82F6', 600: '#2563EB', 700: '#1D4ED8',
    800: '#1E40AF', 900: '#1E3A8A',
  },
} as const;

export const governance = {
  policy: {
    active: '#22C55E',
    draft: '#94A3B8',
    deprecated: '#F59E0B',
    archived: '#64748B',
  },
  decision: {
    approved: '#22C55E',
    denied: '#EF4444',
    escalated: '#F59E0B',
    pending: '#3B82F6',
    override: '#8B5CF6',
  },
  compliance: {
    compliant: '#22C55E',
    nonCompliant: '#EF4444',
    partialCompliant: '#F59E0B',
    notAssessed: '#94A3B8',
  },
} as const;

export const dataViz = {
  categorical: ['#6366F1','#14B8A6','#F59E0B','#EF4444','#3B82F6','#8B5CF6','#EC4899','#10B981','#F97316','#06B6D4'] as const,
  risk: {
    minimal: '#22C55E',
    low: '#84CC16',
    medium: '#F59E0B',
    high: '#F97316',
    critical: '#EF4444',
  },
} as const;

// Dark-mode surface colours (applied via CSS vars; exported for JS consumers)
export const darkSurface = {
  bgPrimary: '#0A0A0A',
  bgSecondary: '#141414',
  bgTertiary: '#1A1A1A',
  bgElevated: '#212121',
  textPrimary: '#FAFAFA',
  textSecondary: '#A3A3A3',
  textTertiary: '#737373',
  border: '#2A2A2A',
  borderStrong: '#3A3A3A',
} as const;
