/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0f1115',
          800: '#16191f',
          700: '#1f242d',
          600: '#2b313d',
        },
        primary: {
          500: '#3b82f6',
          400: '#60a5fa',
        },
        danger: {
          500: '#ef4444',
          400: '#f87171',
        },
        success: {
          500: '#22c55e',
          400: '#4ade80',
        }
      }
    },
  },
  plugins: [],
}
