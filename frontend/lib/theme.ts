/**
 * Theme Configuration - Minimal Modern Design
 *
 * Inspired by Linear, Vercel, Apple - ultra-clean and functional
 * Best Practices: Flat design, subtle shadows, clear hierarchy
 */

export const theme = {
  colors: {
    // Warm beige neutrals - soft, muted tones
    neutral: {
      50: '#FAF9F7',   // Warm white (cream)
      100: '#F5F3F0',  // Soft beige background
      200: '#E8E5E0',  // Warm grey border
      300: '#D4D0C8',  // Muted beige
      400: '#ADA9A0',  // Soft taupe
      500: '#7D7970',  // Warm grey text
      600: '#5C5850',  // Muted brown
      700: '#48443D',  // Dark taupe
      800: '#2F2C27',  // Deep brown
      900: '#1F1C18',  // Almost black (warm)
    },

    // Warm accent - muted brown tones
    accent: {
      50: '#F5F3F0',
      500: '#48443D',   // Dark taupe for primary actions
      600: '#2F2C27',   // Deeper brown on hover
    },

    // Semantic Colors - muted, soft tones
    success: '#6B9B7F',   // Muted sage green
    warning: '#C4A574',   // Soft golden tan
    error: '#B8847A',     // Muted terracotta
    info: '#8799A8',      // Soft blue-grey

    // UI Elements
    background: '#FAF9F7',   // Warm white
    surface: '#F5F3F0',      // Soft beige
    border: '#E8E5E0',       // Warm grey

    // Text - clear hierarchy with warm tones
    text: {
      primary: '#1F1C18',    // Warm dark brown
      secondary: '#5C5850',  // Muted brown
      tertiary: '#ADA9A0',   // Soft taupe
      disabled: '#D4D0C8',   // Muted beige
    }
  },

  // Minimal shadows - barely visible, just for depth
  shadows: {
    none: 'none',
    xs: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    sm: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
  },

  // Subtle rounded corners
  radius: {
    none: '0',
    sm: '0.25rem',   // 4px
    md: '0.375rem',  // 6px
    lg: '0.5rem',    // 8px
    xl: '0.75rem',   // 12px
  },

  // Fast, smooth transitions - not sluggish
  transitions: {
    fast: '100ms cubic-bezier(0.4, 0, 0.2, 1)',
    base: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
  },

  // Spacing scale - 4px grid system
  spacing: {
    xs: '0.25rem',   // 4px
    sm: '0.5rem',    // 8px
    md: '1rem',      // 16px
    lg: '1.5rem',    // 24px
    xl: '2rem',      // 32px
    '2xl': '3rem',   // 48px
  },

  // ESL ambient indicators - soft, warm tints
  esl: {
    approved: 'rgba(107, 155, 127, 0.1)',   // Muted sage green
    vetoed: 'rgba(184, 132, 122, 0.1)',     // Muted terracotta
    modified: 'rgba(135, 153, 168, 0.1)',   // Soft blue-grey
    pulse: 'rgba(31, 28, 24, 0.05)',        // Warm neutral
  },

  // Physics-based animations
  motion: {
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',   // Elastic feel
    magnetic: 'cubic-bezier(0.22, 0.61, 0.36, 1)', // Smooth snap
  }
}

// Best Practice Component Styles - Warm, Soft Palette
export const tw = {
  // Simple solid button - soft brown tones
  primary: 'bg-[#48443D] hover:bg-[#2F2C27] text-white transition-colors duration-150',
  secondary: 'bg-[#F5F3F0] hover:bg-[#E8E5E0] text-[#1F1C18] transition-colors duration-150',
  ghost: 'hover:bg-[#F5F3F0] text-[#5C5850] hover:text-[#1F1C18] transition-colors duration-150',

  // Clean borders - warm grey
  border: 'border-[#E8E5E0]',

  // Text hierarchy - warm browns
  text: {
    primary: 'text-[#1F1C18]',
    secondary: 'text-[#5C5850]',
    tertiary: 'text-[#ADA9A0]',
    disabled: 'text-[#D4D0C8]',
  },

  // Minimal cards - warm cream background
  card: 'bg-[#FAF9F7] border border-[#E8E5E0] rounded-lg hover:border-[#D4D0C8] transition-colors duration-150',

  // Subtle focus states - warm brown
  focus: 'focus:outline-none focus:ring-2 focus:ring-[#48443D] focus:ring-offset-2',

  // Surface - soft beige
  surface: 'bg-[#F5F3F0]',
}

// Typography scale - clear hierarchy with warm tones
export const typography = {
  h1: 'text-3xl font-bold text-[#1F1C18] tracking-tight',
  h2: 'text-2xl font-semibold text-[#1F1C18] tracking-tight',
  h3: 'text-xl font-semibold text-[#1F1C18]',
  h4: 'text-lg font-medium text-[#1F1C18]',
  body: 'text-sm text-[#5C5850]',
  small: 'text-xs text-[#ADA9A0]',
}
