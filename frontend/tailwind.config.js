/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#EEF2F7", 100: "#D6E0EC", 200: "#A9BDD6", 300: "#7B98BD", 400: "#4E73A3",
          500: "#2A5185", 600: "#1D406F", 700: "#13315C", 800: "#0D2445", 900: "#08172D",
        },
        gold: { 400: "#F0BC2E", 500: "#E0A100", 600: "#B88400" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"] },
    },
  },
  plugins: [],
};
