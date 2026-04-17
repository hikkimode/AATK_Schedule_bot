import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "tg-bg": "var(--tg-theme-bg-color)",
        "tg-text": "var(--tg-theme-text-color)",
        "tg-hint": "var(--tg-theme-hint-color)",
        "tg-link": "var(--tg-theme-link-color)",
        "tg-button": "var(--tg-theme-button-color)",
        "tg-secondary": "var(--tg-theme-secondary-bg-color)",
      },
    },
  },
  plugins: [],
};

export default config;
