// Warm Sand Design System — Ethic Companion

export const colors = {
  // Backgrounds
  pageBg: '#FAF8F5',
  sidebarBg: '#F2EDE8',
  surface: '#FFFFFF',
  surfaceBorder: 'rgba(0,0,0,0.04)',

  // Text
  textPrimary: '#1C1917',
  textSecondary: '#78716C',
  textMuted: '#A8A29E',

  // Accent (terracotta)
  accent: '#C2714F',
  accentLight: 'rgba(194,113,79,0.10)',
  accentBorder: 'rgba(194,113,79,0.30)',

  // ESL status
  eslApproved: '#4A7C59',
  eslApprovedBg: 'rgba(74,124,89,0.10)',
  eslVetoed: '#B04A3A',
  eslVetoedBg: 'rgba(176,74,58,0.10)',
  eslModified: '#9B7A3D',
  eslModifiedBg: 'rgba(155,122,61,0.10)',

  // Value type badges
  badgeBoundary: '#C2714F',
  badgeBoundaryBg: 'rgba(194,113,79,0.10)',
  badgePreference: '#4A7C59',
  badgePreferenceBg: 'rgba(74,124,89,0.10)',
  badgeTopicFilter: '#9B7A3D',
  badgeTopicFilterBg: 'rgba(155,122,61,0.10)',
  badgeTimeWindow: '#5B7FA6',
  badgeTimeWindowBg: 'rgba(91,127,166,0.10)',

  // Goal status badges
  statusActive: '#4A7C59',
  statusActiveBg: 'rgba(74,124,89,0.10)',
  statusCompleted: '#1C1917',
  statusCompletedBg: 'rgba(28,25,23,0.10)',
  statusPaused: '#9B7A3D',
  statusPausedBg: 'rgba(155,122,61,0.10)',
  statusArchived: '#A8A29E',
  statusArchivedBg: 'rgba(168,162,158,0.10)',
} as const

export const shadows = {
  card: '0 1px 4px rgba(0,0,0,0.06)',
  cardHover: '0 4px 12px rgba(0,0,0,0.08)',
  toggle: '0 1px 3px rgba(0,0,0,0.12)',
} as const

export const radius = {
  card: '16px',
  button: '8px',
  badge: '6px',
  pill: '9999px',
} as const

export const transition = {
  sidebar: 'all 200ms ease',
  hover: 'all 150ms ease',
} as const
