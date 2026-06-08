/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand accent — remapped onto the existing `teal-*` tokens used
        // throughout the app so the whole UI recolors to Tracktion orange
        // (#FF6A00 primary / #FF8C00 alt) without touching component files.
        teal: {
          50: '#fff3ea',
          100: '#ffe1cc',
          200: '#ffc299',
          300: '#ffa766',
          400: '#ff8c00', // alt orange — links, active nav
          500: '#ff6a00', // primary — focus borders
          600: '#ed6000', // button background
          700: '#c85000', // button hover
          800: '#9e3f00',
          900: '#7a3300', // disabled button background
          950: '#ff6a00', // primary accent token
        },
        // Warm the structural darks toward the brand charcoal tiles
        // (#1A1A1A / #2B2B2B). Light shades kept at Tailwind defaults so
        // text contrast is unchanged.
        slate: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#52525b',
          700: '#3a3a40',
          800: '#232327',
          900: '#1a1a1a',
          950: '#0e0e10',
        },
      },
    },
  },
  plugins: [],
}
