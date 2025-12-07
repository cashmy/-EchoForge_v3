import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: "#0f172a",
        ember: "#ff6b35",
        slate: "#334155",
      },
    },
  },
  plugins: [],
} satisfies Config;
