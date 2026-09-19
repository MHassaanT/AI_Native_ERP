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
          50: "#FCFAF6",   // Canvas background
          100: "#F7F4EE",  // Card / surface background
          200: "#EFEBE2",  // Hover / active highlights
          300: "#E7E2DA",  // Hairline subtle borders
          400: "#D6CEC2",  // Inactive borders / dividers
          500: "#B4A897",
          700: "#57534E",  // Secondary text
          800: "#44403C",  // Muted body text
          900: "#1C1917",  // Primary headings & numbers
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
