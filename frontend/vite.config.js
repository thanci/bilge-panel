import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      // '@/...' ile src/ dizinine kısayol
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // Geliştirme sunucusu — Flask'a proxy
  server: {
    host:   '127.0.0.1',
    port:   5173,
    proxy:  {
      '/api': {
        target:      'http://127.0.0.1:5000',
        changeOrigin: true,
        // CORS hatalarını önle
        configure: (proxy) => {
          proxy.on('error', (err) => console.warn('[Proxy]', err.message))
        },
      },
    },
  },

  // Prod build — /yonetim/ alt dizinine konuşlandırma
  base: '/yonetim/',
  build: {
    outDir:       '../backend/public/yonetim',
    emptyOutDir:  true,
    rollupOptions: {
      output: {
        // Büyük vendor chunk'ları ayır (daha hızlı cache)
        manualChunks: {
          vendor:  ['vue', 'vue-router', 'pinia'],
          http:    ['axios'],
          vueuse:  ['@vueuse/core'],
        },
      },
    },
  },
})
