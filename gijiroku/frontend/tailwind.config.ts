import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f0f4f9",
          100: "#dce5f0",
          600: "#2c4a73",
          700: "#1f3a5f",
          800: "#172d4d",
          900: "#10213a",
        },
      },
    },
  },
  plugins: [],
};
export default config;
