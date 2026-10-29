import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendPort = process.env.BACKEND_PORT || '8010';
const target = `http://127.0.0.1:${backendPort}`;

const proxy = {
  '/app': {
    target,
    changeOrigin: false,
  },
  '/api': {
    target,
    changeOrigin: false,
  },
  '/health': {
    target,
    changeOrigin: false,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    host: '127.0.0.1',
    proxy,
  },
  preview: {
    port: 3000,
    strictPort: true,
    host: '127.0.0.1',
    proxy,
  },
  build: {
    rollupOptions: {
      output: {
        // O entry carregava react + gsap + ícones + markdown num único chunk de
        // 534 KB. Fora do entry, o primeiro paint só paga pelo que usa.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('react-markdown') || id.includes('/remark') || id.includes('micromark') || id.includes('mdast') || id.includes('/unified') || id.includes('hast')) {
            return 'vendor-markdown';
          }
          if (id.includes('gsap')) return 'vendor-gsap';
          if (id.includes('lucide-react')) return 'vendor-icons';
          if (id.includes('/react') || id.includes('scheduler')) return 'vendor-react';
          return 'vendor';
        },
      },
    },
  },
});
