/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        pusher: {
          // New 6-Color Teal Palette
          darkTeal: "#031716",
          pineTeal: "#032F30",
          deepTeal: "#0A7075",
          cyanTeal: "#0C969C",
          steelBlue: "#6BA3BE",
          slateMarine: "#274D60",
          // Previous palette tokens
          taupe: "#A49A87",
          khakiSage: "#A5A58D",
          slateTaupe: "#968F83",
          bone: "#E8E5DF",
          charcoal: "#2F2C27",
          creamLight: "#E8E5DF",
          sage: "#A5A58D",
          oliveDark: "#968F83",
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
