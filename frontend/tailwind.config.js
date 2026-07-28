/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  corePlugins: {
    // Ant Design ships its own preflight; keep both stacks from fighting.
    preflight: false,
  },
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Satoshi',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'sans-serif',
        ],
      },
      colors: {
        background: '#F7FAF8',
        foreground: '#0F1B14',
      },
    },
  },
  plugins: [],
};
