/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: '#facc15',
          dark:    '#f59e0b',
          muted:   'rgba(250,204,21,0.1)',
        },
        surface: {
          DEFAULT: '#141408',
          hover:   '#1e1e0a',
          border:  '#222210',
        },
        bg: '#0a0a06',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'accent-gradient': 'linear-gradient(135deg, #facc15, #f59e0b)',
      },
    },
  },
  plugins: [],
}