import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: "#000000",
        panel: "#0F0F0F",
        elevated: "#1A1A1A",
        input: "#262626",
        primary: "#D1D4DC",
        secondary: "#B2B5BE",
        muted: "#787B86",
        accent: "#2962FF",
        "accent-hover": "#1E53E5",
        bull: "#26A69A",
        bear: "#EF5350",
        border: "#1F1F1F",
        "border-strong": "#2E2E2E",
      },
      borderRadius: {
        DEFAULT: "4px",
      },
      boxShadow: {
        float: "0 2px 8px rgba(0,0,0,0.4)",
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Inter",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
