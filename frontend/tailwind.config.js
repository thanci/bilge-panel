/** @type {import('tailwindcss').Config} */
export default {
  // Yalnızca kullanılan sınıfları dahil et (tree-shaking)
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],

  // Karanlık mod: class tabanlı ('dark' sınıfı html etiketine eklenir)
  darkMode: 'class',

  theme: {
    extend: {
      // Bilge Yolcu renk paleti
      colors: {
        // Arkaplan katmanları
        surface: {
          base:    '#030712',   // En derin zemin (gray-950)
          DEFAULT: '#111827',   // Ana sayfa arka planı (gray-900)
          raised:  '#1f2937',   // Kart yüzeyi (gray-800)
          hover:   '#374151',   // Hover durumu (gray-700)
        },
        // Vurgu rengi — akıl, derinlik sembolü
        accent: {
          DEFAULT: '#6366f1',   // indigo-500
          light:   '#818cf8',   // indigo-400
          dark:    '#4f46e5',   // indigo-600
          muted:   '#6366f120', // %12 opasite (badge bg)
        },
        // Durum renkleri
        success:  '#10b981',   // emerald-500
        warning:  '#f59e0b',   // amber-500
        danger:   '#ef4444',   // red-500
        info:     '#0ea5e9',   // sky-500
      },

      // Google Fonts (index.html'de import edilir)
      fontFamily: {
        sans:  ['Inter', 'system-ui', 'sans-serif'],
        mono:  ['JetBrains Mono', 'Fira Code', 'monospace'],
      },

      // Özel animasyonlar
      animation: {
        'fade-in':      'fadeIn 0.3s ease-out',
        'slide-up':     'slideUp 0.3s ease-out',
        'pulse-slow':   'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow':    'spin 2s linear infinite',
        'gauge-fill':   'gaugeFill 1.2s ease-out forwards',
      },
      keyframes: {
        fadeIn:    { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:   { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        gaugeFill: { from: { strokeDashoffset: '251.2' }, to: { strokeDashoffset: 'var(--gauge-offset)' } },
      },

      // Özel box-shadow'lar
      boxShadow: {
        'card':      '0 4px 24px rgba(0, 0, 0, 0.4)',
        'card-hover':'0 8px 32px rgba(0, 0, 0, 0.5)',
        'glow':      '0 0 20px rgba(99, 102, 241, 0.3)',
        'glow-sm':   '0 0 8px rgba(99, 102, 241, 0.2)',
      },

      // Özel border-radius
      borderRadius: {
        'xl2': '1rem',
        'xl3': '1.5rem',
      },
    },
  },

  // Dinamik class'lar için safelist
  // (JS'de string concatenation ile oluşturulanlar)
  safelist: [
    // StatusBadge durumları
    'bg-slate-600', 'text-slate-200',
    'bg-indigo-500/20', 'text-indigo-400',
    'bg-emerald-500/20', 'text-emerald-400',
    'bg-red-500/20', 'text-red-400',
    'bg-amber-500/20', 'text-amber-400',
    'bg-sky-500/20', 'text-sky-400',
    // BudgetGauge renkleri
    'stroke-emerald-500', 'stroke-amber-500',
    'stroke-orange-500', 'stroke-red-500',
    'text-emerald-400', 'text-amber-400', 'text-red-400',
  ],

  plugins: [
    require('@tailwindcss/forms'),
  ],
}
