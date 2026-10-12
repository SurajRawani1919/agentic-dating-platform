/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0908",
          900: "#12100e",
          800: "#1c1916",
          700: "#2a2521",
          600: "#3d3630",
        },
        ivory: {
          50: "#faf7f2",
          100: "#f3eee4",
          200: "#e8dfd0",
          300: "#d4c7b0",
        },
        champagne: {
          400: "#d4b896",
          500: "#c4a574",
          600: "#a88756",
        },
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', "Georgia", "serif"],
        sans: ['"Outfit"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 0 rgba(212,184,150,0.08)",
      },
    },
  },
  plugins: [],
};
