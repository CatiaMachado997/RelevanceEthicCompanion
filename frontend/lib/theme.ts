// Design System — Ethic Companion (neutral gray + sage green accent)

export const colors = {
  // Backgrounds
  pageBg: '#ffffff',
  sidebarBg: '#fafafa',
  surface: '#ffffff',
  surfaceBorder: '#e5e5e5',

  // Text
  textPrimary: '#1a1a1a',
  textSecondary: '#6b6b6b',
  textMuted: '#9e9e9e',

  // Accent (neutral dark)
  accent: '#1a1a1a',
  accentLight: 'rgba(26,26,26,0.05)',
  accentBorder: '#e5e5e5',

  // ESL status (unchanged — functional colors)
  eslApproved: '#4A7C59',
  eslApprovedBg: 'rgba(74,124,89,0.10)',
  eslVetoed: '#B04A3A',
  eslVetoedBg: 'rgba(176,74,58,0.10)',
  eslModified: '#9B7A3D',
  eslModifiedBg: 'rgba(155,122,61,0.10)',

  // Value type badges — monochrome (boundary) + functional (others)
  badgeBoundary: '#1a1a1a',
  badgeBoundaryBg: 'rgba(26,26,26,0.06)',
  badgePreference: '#4A7C59',
  badgePreferenceBg: 'rgba(74,124,89,0.10)',
  badgeTopicFilter: '#9B7A3D',
  badgeTopicFilterBg: 'rgba(155,122,61,0.10)',
  badgeTimeWindow: '#5B7FA6',
  badgeTimeWindowBg: 'rgba(91,127,166,0.10)',

  // Goal status badges
  statusActive: '#4A7C59',
  statusActiveBg: 'rgba(74,124,89,0.10)',
  statusCompleted: '#1a1a1a',
  statusCompletedBg: 'rgba(26,26,26,0.08)',
  statusPaused: '#9B7A3D',
  statusPausedBg: 'rgba(155,122,61,0.10)',
  statusArchived: '#9e9e9e',
  statusArchivedBg: 'rgba(158,158,158,0.10)',
} as const

export const shadows = {
  card: '0 1px 3px rgba(0,0,0,0.08)',
  cardHover: '0 4px 12px rgba(0,0,0,0.10)',
  toggle: '0 1px 3px rgba(0,0,0,0.12)',
} as const

export const radius = {
  card: '16px',
  button: '20px',
  badge: '6px',
  pill: '9999px',
} as const

export const transition = {
  sidebar: 'all 200ms ease',
  hover: 'all 150ms ease',
} as const
