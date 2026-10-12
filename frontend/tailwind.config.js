/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eaf0f8',
          100: '#dbe6f5',
          200: '#b9cbe5',
          300: '#8ea9d0',
          400: '#5278b2',
          500: '#102f6b',
          600: '#0b2a5b',
          700: '#092247',
          800: '#071a36',
          900: '#051326',
          950: '#030b18',
        },
        navy: {
          800: '#102f6b',
          900: '#0b2a5b',
          950: '#071a36',
        },
        bg: '#f3f5f7',
        surface: '#ffffff',
        surface2: '#eaf0f8',
        accent: '#102f6b',
        accentSoft: '#f4a300',
        cyan: '#102f6b',
        violet: '#e89b00',
      },
      boxShadow: {
        glow: '0 8px 24px rgba(16,47,107,0.06)',
        cyan: '0 8px 24px rgba(16,47,107,0.06)',
      },
      backgroundImage: {
        'hero-radial': 'radial-gradient(circle at top, rgba(16,47,107,0.08), transparent 35%), radial-gradient(circle at 80% 20%, rgba(232,155,0,0.08), transparent 28%)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        float: 'float 6s ease-in-out infinite',
        'float-slow': 'floatSlow 10s ease-in-out infinite',
        pulseLine: 'pulseLine 5s ease-in-out infinite',
        orbit: 'orbit 18s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        floatSlow: {
          '0%, 100%': { transform: 'translate3d(0,0,0)' },
          '50%': { transform: 'translate3d(0,-20px,0)' },
        },
        pulseLine: {
          '0%,100%': { opacity: '0.32' },
          '50%': { opacity: '0.9' },
        },
        orbit: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      }
    },
  },
  plugins: [],
};
