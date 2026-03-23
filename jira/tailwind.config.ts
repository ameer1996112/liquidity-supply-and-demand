import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0d0f14',
        surface:  '#13161e',
        raised:   '#1a1d28',
        border:   '#1f2335',
        text: {
          primary:   '#e2e8f0',
          secondary: '#94a3b8',
          dim:       '#475569',
        },
        accent:   '#f59e0b',
        violet:   '#8b5cf6',
        blue:     '#3b82f6',
        emerald:  '#10b981',
        rose:     '#ef4444',
        amber:    '#f59e0b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-in': 'slideIn 0.2s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideIn: { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
      },
    },
  },
  plugins: [],
};

export default config;
