/** Configuración Tailwind de Proyecto Córdoba.
 *  Content incluye los .py porque algunas vistas componen clases
 *  (badges de confianza OCR, filas HTMX) desde Python.
 */
module.exports = {
  darkMode: 'class',
  content: [
    '../templates/**/*.html',
    '../apps/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#f0f5ff',
          100: '#e0ebff',
          200: '#c1d9ff',
          300: '#a2c7ff',
          400: '#83b5ff',
          500: '#0051c4',
          600: '#003fa3',
          700: '#002d7a',
          800: '#001b51',
          900: '#000d28',
        },
        secondary: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#00a556',
          600: '#008c45',
          700: '#007234',
          800: '#005823',
          900: '#004012',
        },
        accent: {
          50:  '#faf9f6',
          100: '#f5f2ed',
          200: '#ebe5db',
          300: '#ddd4c5',
          400: '#cfc3af',
          500: '#b8a99a',
          600: '#9d8f85',
          700: '#82756a',
          800: '#675c50',
          900: '#4c4238',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
