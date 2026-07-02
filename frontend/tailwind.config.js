/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#fdf4ff',
          100: '#fae8ff',
          200: '#f3d0fe',
          300: '#e9a8fc',
          400: '#d879f7',
          500: '#c044eb',
          600: '#a21bcf',
          700: '#871baa',
          800: '#701b8a',
          900: '#5a1870',
        },
        surface: {
          DEFAULT: '#0a0a0f',
          50:  '#f8f8fa',
          100: '#1a1a2e',
          200: '#16213e',
          300: '#0f3460',
        },
        emotion: {
          joy:      '#f9c74f',
          sadness:  '#577590',
          anger:    '#f94144',
          fear:     '#9b5de5',
          disgust:  '#43aa8b',
          surprise: '#f8961e',
          neutral:  '#6b7280',
        }
      },
      fontFamily: {
        display: ['"DM Serif Display"', 'serif'],
        body: ['"DM Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease forwards',
        'slide-up': 'slideUp 0.4s ease forwards',
        'pulse-ring': 'pulseRing 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(192, 68, 235, 0.4)' },
          '50%': { boxShadow: '0 0 0 12px rgba(192, 68, 235, 0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        }
      }
    },
  },
  plugins: [],
}
