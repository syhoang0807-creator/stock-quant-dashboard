/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bull-green": "#00C851",
        "bear-red":   "#FF4444",
        "neutral":    "#94a3b8",
        "bg-dark":    "#0f172a",
        "card-dark":  "#1e293b",
        "border-dark":"#334155",
      },
    },
  },
  plugins: [],
};
