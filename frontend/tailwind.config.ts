import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Палитра под платформу ai.knus.edu.kz (нейтральная, деловая).
        risk: {
          high: "#dc2626",
          medium: "#d97706",
          low: "#16a34a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
