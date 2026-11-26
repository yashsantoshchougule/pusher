/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: Object.fromEntries(
        ['canvas', 'surface', 'field', 'ink', 'muted', 'line', 'control', 'primary', 'primary-hover', 'nav', 'nav-ink', 'soft', 'accent', 'accent-ink']
          .map(name => [name, `rgb(var(--ui-${name}) / <alpha-value>)`]),
      ),
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
