/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#1E293B", dark: "#0F172A", light: "#334155" },
      },
    },
  },
  plugins: [],
};
