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
          50: '#F5F6F8',
          100: '#EEF1F5',
          200: '#E3E7ED',
          300: '#D0D5DD',
          400: '#667085',
          500: '#17243A',
          600: '#101B2D',
          700: '#0D1624',
          800: '#0A111D',
          900: '#07101B',
          950: '#04080F',
        },
        navy: {
          800: '#17243A',
          900: '#101B2D',
          950: '#0A111D',
        },
        bg: '#F5F6F8',
        surface: '#FFFFFF',
        surface2: '#EEF1F5',
        accent: '#17243A',
        accentSoft: '#C6A15B',
        cyan: '#315E9B',
        violet: '#C6A15B',
      },
      boxShadow: {
        glow: '0 4px 16px rgba(23,36,58,0.045)',
        cyan: '0 4px 16px rgba(23,36,58,0.045)',
      },
      backgroundImage: {
        'hero-radial': 'radial-gradient(circle at top, rgba(23,36,58,0.08), transparent 35%), radial-gradient(circle at 80% 20%, rgba(198,161,91,0.08), transparent 28%)',
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
