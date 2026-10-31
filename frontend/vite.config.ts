import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// BACKEND_URL aponta o dev server para o backend publicado (https) e
// BACKEND_API_KEY injeta a credencial no proxy (server-side), sem expor no bundle.
// Lidos de variavel de ambiente ou de frontend/.env.local (gitignored).
export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '');
  const backendPort = process.env.BACKEND_PORT || fileEnv.BACKEND_PORT || '8010';
  const target =
    process.env.BACKEND_URL || fileEnv.BACKEND_URL || `http://127.0.0.1:${backendPort}`;
  const backendApiKey = process.env.BACKEND_API_KEY || fileEnv.BACKEND_API_KEY || '';
  const injectedHeaders: Record<string, string> = backendApiKey
    ? { 'x-api-key': backendApiKey }
    : {};

// O backend só emite sessão para Host loopback. No dev, o proxy se apresenta
// como 127.0.0.1 para permitir testar pelo celular via túnel/LAN.
const proxy = {
  '/app': {
    target,
    secure: false,
    headers: injectedHeaders,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on('proxyReq', (req) => {
        req.setHeader('origin', target);
        req.setHeader('referer', `${target}/`);
        req.setHeader('x-forwarded-proto', 'http');
        req.removeHeader('x-forwarded-for');
        req.removeHeader('x-real-ip');
      });
    },
  },
  '/api': {
    target,
    secure: false,
    headers: injectedHeaders,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on('proxyReq', (req) => {
        req.setHeader('origin', target);
        req.setHeader('referer', `${target}/`);
        req.setHeader('x-forwarded-proto', 'http');
        req.removeHeader('x-forwarded-for');
        req.removeHeader('x-real-ip');
      });
    },
  },
  '/health': {
    target,
    secure: false,
    headers: injectedHeaders,
    changeOrigin: true,
  },
};

return {
  plugins: [react()],
  server: {
    allowedHosts: true,
    port: 3002,
    strictPort: true,
    host: '0.0.0.0',
    proxy,
  },
  preview: {
    allowedHosts: true,
    port: 3002,
    strictPort: true,
    host: '0.0.0.0',
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
          if (id.includes('lucide-react')) return 'vendor-icons';
          if (id.includes('/react') || id.includes('scheduler')) return 'vendor-react';
          return 'vendor';
        },
      },
    },
  },
  };
});
