import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          50: "#F7F8F6",   // Canvas background
          100: "#F1F3F0",  // Muted surface background
          200: "#E8ECE7",  // Hover / active highlights
          300: "#E1E5E0",  // Hairline subtle borders
          400: "#CDD4CD",  // Inactive borders / dividers
          500: "#AEB8AE",
          700: "#5C665E",  // Secondary text
          800: "#414A43",  // Muted body text
          900: "#202923",  // Primary headings & numbers
        },
        sage: {
          50: "#F2F6F3",
          100: "#E4EDE6",
          500: "#3F6249",
          700: "#2B4433",
        },
        terracotta: {
          50: "#FAF0EE",
          100: "#F5DFDB",
          500: "#9E4738",
          700: "#703024",
        },
        amberGold: {
          50: "#FDF8F0",
          100: "#FAEFDD",
          500: "#9A6724",
          700: "#6B4616",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
