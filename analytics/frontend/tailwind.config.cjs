/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: '#182e58',      // Main chatbot UI theme
          teal: '#2D7A8E',      // Teal from logo (kept for references)
          green: '#4CAF50',     // Green accent (kept for references)
          'navy-light': '#2a4d94', // Light variant for #182e58
          'teal-light': '#3D9AAE',
          'green-light': '#66BB6A',
        }
      }
    }
  },
  plugins: []
};

