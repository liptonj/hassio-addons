/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "media",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        meraki: {
          blue: '#00a4e4',
          'blue-dark': '#0078a8',
          'blue-light': '#e6f7fd',
        },
        gray: {
          50: '#fafbfc',
          100: '#f7fafc',
          200: '#edf2f7',
          300: '#e2e8f0',
          400: '#cbd5e0',
          500: '#a0aec0',
          600: '#718096',
          700: '#4a5568',
          800: '#2d3748',
          900: '#1a202c',
        },
        success: {
          DEFAULT: '#48bb78',
          light: '#d1fae5',
        },
        warning: {
          DEFAULT: '#ecc94b',
          light: '#fef3c7',
        },
        danger: {
          DEFAULT: '#ef4444',
          light: '#fee2e2',
        },
        error: {
          DEFAULT: '#ef4444',
          light: '#fee2e2',
        },
        info: {
          DEFAULT: '#4299e1',
          light: '#bee3f8',
        },
      },
      fontFamily: {
        sans: ['DM Sans', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Monaco', 'monospace'],
      },
      borderRadius: {
        'DEFAULT': '10px',
        'lg': '12px',
        'xl': '16px',
      },
      boxShadow: {
        'card': '0 2px 8px rgba(0, 0, 0, 0.08)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.12)',
        'button': '0 4px 12px rgba(0, 164, 228, 0.3)',
        'button-hover': '0 6px 20px rgba(0, 164, 228, 0.4)',
      },
      backgroundImage: {
        'meraki-gradient': 'linear-gradient(135deg, #00a4e4 0%, #0078a8 100%)',
        'primary-gradient': 'linear-gradient(135deg, #00a4e4, #0056b3)',
        'danger-gradient': 'linear-gradient(135deg, #ef4444, #b91c1c)',
      },
    },
  },
  plugins: [],
}
