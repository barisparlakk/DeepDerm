// DeepDerm Design Tokens
export const colors = {
  primary:     '#0EA5E9',   // Sky blue
  primaryDark: '#0284C7',
  primaryLight:'#E0F2FE',
  accent:      '#10B981',   // Emerald
  accentLight: '#D1FAE5',
  danger:      '#EF4444',
  dangerDark:  '#DC2626',
  dangerLight: '#FEE2E2',
  warning:     '#F59E0B',
  warningLight:'#FEF3C7',
  text:        '#0F172A',
  textSecond:  '#64748B',
  textMuted:   '#94A3B8',
  background:  '#F8FAFC',
  surface:     '#FFFFFF',
  border:      '#E2E8F0',
  borderLight: '#F1F5F9',
} as const;

export const spacing = {
  xs:  4,
  sm:  8,
  md:  16,
  lg:  24,
  xl:  32,
  xxl: 48,
} as const;

export const radius = {
  sm:  8,
  md:  12,
  lg:  16,
  xl:  24,
  full: 999,
} as const;

export const shadow = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
} as const;
