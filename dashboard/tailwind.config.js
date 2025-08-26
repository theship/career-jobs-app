/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#000000',
        surface: {
          DEFAULT: '#111111',
          hover: '#1A1A1A',
        },
        border: {
          DEFAULT: '#2A2A2A',
          hover: '#444444',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#A0A0A0',
          muted: '#666666',
        },
        accent: {
          red: {
            DEFAULT: '#EF4444',
            dark: '#DC2626',
            light: '#FCA5A5',
            muted: '#991B1B',
          }
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-radial-dark': 'radial-gradient(circle at center, #111111 0%, #000000 100%)',
        'gradient-red-subtle': 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, transparent 100%)',
        'gradient-red-button': 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-red': '0 0 20px rgba(239, 68, 68, 0.3)',
        'glow-red-hover': '0 0 30px rgba(239, 68, 68, 0.4)',
      }
    },
  },
  plugins: [],
}