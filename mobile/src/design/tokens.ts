/** save:on design tokens — extend existing theme without breaking legacy styles. */
import { theme } from '../theme';

export const ui = {
  color: {
    background: theme.bg,
    surface: theme.card,
    foreground: theme.text,
    secondaryText: theme.muted,
    border: theme.line,
    brand: theme.primary,
    brandSoft: theme.primarySoft,
    success: theme.accent,
    warning: '#A86D25',
    error: '#B84C4C',
    neutralSoft: '#F4F5F9',
    errorSoft: '#FFF2F0',
    white: '#FFFFFF',
  },
  spacing: { xxs: 4, xs: 8, sm: 12, md: 16, lg: 20, xl: 24, xxl: 32 },
  radius: { sm: 10, md: 14, lg: 18, xl: 22, pill: 999 },
  type: {
    caption: 12,
    body: 14,
    label: 14,
    section: 18,
    screen: 24,
  },
  minTouchTarget: 44,
} as const;
