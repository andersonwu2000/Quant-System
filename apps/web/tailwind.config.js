/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Geist Mono', 'SF Mono', 'monospace'],
      },
      colors: {
        surface: {
          0: '#0a0a0a',
          1: '#111111',
          2: '#1a1a1a',
          3: '#262626',
        },
        profit: { DEFAULT: '#ef4444', soft: '#7f1d1d' },   // 台灣：紅=漲
        loss:   { DEFAULT: '#10b981', soft: '#065f46' },    // 台灣：綠=跌
      },
      borderRadius: { card: '8px' },
      fontSize: {
        data: ['13px', { lineHeight: '20px', fontWeight: '500' }],
      },
      keyframes: {
        'flash-profit': {
          '0%': { backgroundColor: 'rgba(239,68,68,0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'flash-loss': {
          '0%': { backgroundColor: 'rgba(16,185,129,0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'pulse-dot': {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        'flash-profit': 'flash-profit 0.6s ease-out',
        'flash-loss': 'flash-loss 0.6s ease-out',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
